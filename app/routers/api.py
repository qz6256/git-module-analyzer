"""JSON API：仓库管理、分析触发、任务状态、配置、文件/提交检索、需求缺陷追溯。"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import analyzer, git_service, issue_linker, llm_service
from ..database import REPOS_DIR, get_db
from ..models import (BranchState, CommitAnalysis, FileChangeEvent, Issue, IssueCommitLink,
                      ModuleCandidate, ModuleChangeEvent, ProjectModule, Repository,
                      SourceFile, SystemConfig)
from ..schemas import (ConfigUpdate, InitRequest, IssueCreate, IssueImport,
                       RepoCreate, SyncRequest)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    return {"ok": True, "version": "1.0.0"}


# ---------------- 系统配置 ----------------

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    cfg = llm_service.get_config(db)
    key = cfg.api_key or ""
    return {"base_url": cfg.base_url, "api_key": key, "api_key_masked": _mask(key),
            "model": cfg.model, "max_diff_chars": cfg.max_diff_chars,
            "commit_web_base_url": cfg.commit_web_base_url, "llm_enabled": cfg.llm_enabled,
            "mode": "LLM" if (cfg.llm_enabled and key) else "本地规则"}


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:4] + "*" * max(0, min(len(key) - 8, 20)) + key[-4:] if len(key) > 8 else "****"


@router.put("/config")
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)):
    cfg = llm_service.get_config(db)
    cfg.base_url = payload.base_url.strip() or "https://api.openai.com/v1"
    # 前端回传掩码时不覆盖真实 Key
    if payload.api_key and "*" not in payload.api_key:
        cfg.api_key = payload.api_key.strip()
    elif payload.api_key == "":
        cfg.api_key = ""
    cfg.model = payload.model.strip() or "gpt-4o-mini"
    cfg.max_diff_chars = payload.max_diff_chars
    cfg.commit_web_base_url = payload.commit_web_base_url.strip()
    cfg.llm_enabled = payload.llm_enabled
    db.commit()
    return {"ok": True, "mode": "LLM" if (cfg.llm_enabled and cfg.api_key) else "本地规则"}


@router.post("/config/test")
def test_config(db: Session = Depends(get_db)):
    cfg = llm_service.get_config(db)
    ok, msg = llm_service.test_connection(cfg)
    return {"ok": ok, "message": msg}


# ---------------- 仓库管理 ----------------

@router.get("/repos")
def list_repos(db: Session = Depends(get_db)):
    repos = db.scalars(select(Repository).order_by(Repository.id.desc())).all()
    out = []
    for r in repos:
        out.append({
            "id": r.id, "name": r.name, "source": r.source, "source_type": r.source_type,
            "local_path": r.local_path, "default_branch": r.default_branch,
            "branches": r.branches or [], "status": r.status,
            "status_message": r.status_message,
            "last_analyzed_at": r.last_analyzed_at.isoformat() if r.last_analyzed_at else None,
            "file_count": db.scalar(select(func.count()).select_from(SourceFile)
                                    .where(SourceFile.repo_id == r.id)) or 0,
            "module_count": db.scalar(select(func.count()).select_from(ProjectModule)
                                      .where(ProjectModule.repo_id == r.id)) or 0,
            "commit_count": db.scalar(select(func.count()).select_from(CommitAnalysis)
                                      .where(CommitAnalysis.repo_id == r.id,
                                             CommitAnalysis.is_high_signal.is_(True))) or 0,
        })
    return {"items": out}


@router.post("/repos")
def create_repo(payload: RepoCreate, db: Session = Depends(get_db)):
    source = payload.source.strip()
    name = payload.name.strip()
    if payload.source_type == "local":
        path = git_service.normalize_local_path(source)
        if not Path(path).exists():
            raise HTTPException(400, f"路径不存在：{path}")
        if not git_service.is_git_repo(path):
            raise HTTPException(400, f"不是有效的 Git 仓库：{path}")
        local_path = path
        if not name:
            name = Path(path).name
        branches = payload.branches or [payload.default_branch]
        # 自动探测真实主分支
        detected = git_service.current_branch(path)
        if payload.default_branch not in ("main", "master") or detected not in branches:
            if detected and detected not in ("HEAD", ""):
                branches = [detected] + [b for b in branches if b != detected]
    else:
        local_path = ""
        if not name:
            name = source.rstrip("/").split("/")[-1].removesuffix(".git")
        branches = payload.branches or [payload.default_branch]
    repo = Repository(name=name, source=source, source_type=payload.source_type,
                      local_path=local_path, default_branch=branches[0],
                      branches=list(dict.fromkeys(branches)), status="pending")
    db.add(repo)
    db.commit()
    return {"ok": True, "id": repo.id, "name": repo.name, "branches": repo.branches}


@router.get("/repos/{repo_id}")
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    r = db.get(Repository, repo_id)
    if not r:
        raise HTTPException(404, "仓库不存在")
    states = db.scalars(select(BranchState).where(BranchState.repo_id == repo_id)).all()
    return {"id": r.id, "name": r.name, "source": r.source, "source_type": r.source_type,
            "local_path": r.local_path, "default_branch": r.default_branch,
            "branches": r.branches or [], "available_branches": git_service.list_branches(r.local_path)
            if r.local_path and git_service.is_git_repo(r.local_path) else [],
            "status": r.status, "status_message": r.status_message,
            "branch_states": [{"branch": s.branch, "last_commit_sha": s.last_commit_sha}
                              for s in states]}


@router.put("/repos/{repo_id}")
def update_repo(repo_id: int, payload: dict, db: Session = Depends(get_db)):
    r = db.get(Repository, repo_id)
    if not r:
        raise HTTPException(404, "仓库不存在")
    if "branches" in payload and isinstance(payload["branches"], list):
        r.branches = [str(x).strip() for x in payload["branches"] if str(x).strip()]
        if r.branches:
            r.default_branch = r.branches[0]
    if "name" in payload and str(payload["name"]).strip():
        r.name = str(payload["name"]).strip()
    db.commit()
    return {"ok": True, "branches": r.branches}


@router.delete("/repos/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db)):
    r = db.get(Repository, repo_id)
    if not r:
        raise HTTPException(404, "仓库不存在")
    for model in (FileChangeEvent, CommitAnalysis, SourceFile, ProjectModule, BranchState,
                  ModuleChangeEvent, ModuleCandidate, IssueCommitLink, Issue):
        db.query(model).filter(model.repo_id == repo_id).delete()
    db.delete(r)
    db.commit()
    if r.source_type == "remote":
        target = REPOS_DIR / str(repo_id)
        if target.exists() and str(target).startswith(str(REPOS_DIR)):
            shutil.rmtree(target, ignore_errors=True)
    return {"ok": True}


@router.post("/repos/{repo_id}/initialize")
def init_repo(repo_id: int, payload: InitRequest | None = None, db: Session = Depends(get_db)):
    r = db.get(Repository, repo_id)
    if not r:
        raise HTTPException(404, "仓库不存在")
    p = payload or InitRequest()
    jid = analyzer.jobs.create("initialize", repo_id)
    analyzer.jobs.start(jid, "initialize", repo_id,
                        history_limit=p.history_limit, max_files=p.max_files)
    return {"ok": True, "job_id": jid}


@router.post("/repos/{repo_id}/sync")
def sync_repo(repo_id: int, payload: SyncRequest | None = None, db: Session = Depends(get_db)):
    r = db.get(Repository, repo_id)
    if not r:
        raise HTTPException(404, "仓库不存在")
    if not r.local_path:
        raise HTTPException(400, "请先执行初始化扫描")
    p = payload or SyncRequest()
    jid = analyzer.jobs.create("sync", repo_id)
    analyzer.jobs.start(jid, "sync", repo_id, branch=p.branch,
                        force_rebuild=p.force_rebuild)
    return {"ok": True, "job_id": jid}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    j = analyzer.jobs.get(job_id)
    if not j:
        raise HTTPException(404, "任务不存在")
    return j


# ---------------- 概览统计 ----------------

@router.get("/stats")
def stats(repo_id: int = 0, db: Session = Depends(get_db)):
    def count(model, *conds):
        q = select(func.count()).select_from(model)
        if repo_id:
            q = q.where(model.repo_id == repo_id)
        for c in conds:
            q = q.where(c)
        return db.scalar(q) or 0
    return {
        "repos": count(Repository) if not repo_id else 1,
        "modules": count(ProjectModule),
        "files": count(SourceFile),
        "events": count(FileChangeEvent),
        "commits": count(CommitAnalysis),
        "high_signal_commits": count(CommitAnalysis, CommitAnalysis.is_high_signal.is_(True)),
        "filtered_commits": count(CommitAnalysis, CommitAnalysis.is_high_signal.is_(False)),
        "branches": count(BranchState),
        "high_risk_files": count(SourceFile, SourceFile.risk_level == "高"),
        "module_events": count(ModuleChangeEvent),
        "pending_candidates": count(ModuleCandidate,
                                    ModuleCandidate.status == "pending"),
        "issues": count(Issue),
        "issue_links": count(IssueCommitLink),
        "pending_issue_reviews": count(IssueCommitLink,
                                       IssueCommitLink.review_status == "pending"),
        "strong_evidence": count(IssueCommitLink,
                                 IssueCommitLink.assessment == "strong",
                                 IssueCommitLink.review_status != "rejected"),
        "need_review": count(IssueCommitLink,
                             IssueCommitLink.assessment == "review",
                             IssueCommitLink.review_status != "rejected"),
    }


# ---------------- 模块 / 文件 ----------------

@router.get("/repos/{repo_id}/modules")
def list_modules(repo_id: int, db: Session = Depends(get_db)):
    items = db.scalars(select(ProjectModule).where(ProjectModule.repo_id == repo_id)
                       .order_by(ProjectModule.id)).all()
    return {"items": [{"id": m.id, "name": m.name, "path_rules": m.path_rules or [],
                       "responsibility": m.responsibility, "one_liner": m.one_liner,
                       "evolution_line": m.evolution_line, "status": m.status,
                       "change_count": m.change_count, "file_count": m.file_count,
                       "doc_path": m.doc_path} for m in items]}


@router.get("/modules/{module_id}")
def module_detail(module_id: int, branch: str = "", db: Session = Depends(get_db)):
    m = db.get(ProjectModule, module_id)
    if not m:
        raise HTTPException(404, "模块不存在")
    cfg = llm_service.get_config(db)
    conds = [ModuleChangeEvent.module_id == module_id]
    if branch:
        conds.append(ModuleChangeEvent.branch == branch)
    events = db.scalars(select(ModuleChangeEvent).where(*conds)
                        .order_by(ModuleChangeEvent.committed_at.desc().nullslast(),
                                  ModuleChangeEvent.id.desc())).all()
    files = db.scalars(select(SourceFile).where(SourceFile.repo_id == m.repo_id,
                                                SourceFile.module_name == m.name)
                       .order_by(SourceFile.change_count.desc(), SourceFile.path)).all()
    branches = [b for b in db.scalars(select(ModuleChangeEvent.branch)
                                      .where(ModuleChangeEvent.module_id == module_id)
                                      .distinct()).all() if b]
    base = (cfg.commit_web_base_url or "").strip().rstrip("/")
    return {
        "module": {"id": m.id, "name": m.name, "repo_id": m.repo_id,
                   "path_rules": m.path_rules or [], "responsibility": m.responsibility,
                   "one_liner": m.one_liner, "current_doc": m.current_doc,
                   "evolution_line": m.evolution_line, "status": m.status,
                   "change_count": m.change_count, "file_count": m.file_count,
                   "doc_path": m.doc_path, "last_commit_sha": m.last_commit_sha},
        "commit_base": base, "branches": branches,
        "files": [{"id": f.id, "path": f.path, "one_liner": f.one_liner,
                   "change_count": f.change_count, "risk_level": f.risk_level}
                  for f in files],
        "events": [{
            "id": e.id, "commit_sha": e.commit_sha, "sha_short": e.commit_sha[:7],
            "branch": e.branch, "author": e.author,
            "committed_at": e.committed_at.isoformat() if e.committed_at else "",
            "commit_message": e.commit_message, "summary": e.summary,
            "capability_delta": e.capability_delta,
            "affected_files": e.affected_files or [], "motivation": e.motivation,
            "evidence_source": e.evidence_source, "risk_level": e.risk_level,
            "analysis_mode": e.analysis_mode,
        } for e in events],
    }


@router.get("/repos/{repo_id}/module-candidates")
def list_module_candidates(repo_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(ModuleCandidate).where(ModuleCandidate.repo_id == repo_id)
                      .order_by(ModuleCandidate.id.desc())).all()
    return {"items": [{"id": c.id, "name": c.name, "path_rules": c.path_rules or [],
                       "reason": c.reason, "evidence_commit": c.evidence_commit,
                       "sample_files": c.sample_files or [], "status": c.status,
                       "created_at": c.created_at.isoformat() if c.created_at else ""}
                      for c in rows]}


@router.post("/module-candidates/{candidate_id}/confirm")
def confirm_module_candidate(candidate_id: int, payload: dict | None = None,
                             db: Session = Depends(get_db)):
    try:
        return analyzer.confirm_candidate(db, candidate_id,
                                          (payload or {}).get("name", ""))
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/module-candidates/{candidate_id}/ignore")
def ignore_module_candidate(candidate_id: int, db: Session = Depends(get_db)):
    try:
        return analyzer.ignore_candidate(db, candidate_id)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/repos/{repo_id}/files")
def list_files(repo_id: int, q: str = "", module: str = "", risk: str = "",
               page: int = 1, size: int = 30, db: Session = Depends(get_db)):
    conds = [SourceFile.repo_id == repo_id]
    if q:
        conds.append(or_(SourceFile.path.contains(q), SourceFile.one_liner.contains(q)))
    if module:
        conds.append(SourceFile.module_name == module)
    if risk:
        conds.append(SourceFile.risk_level == risk)
    total = db.scalar(select(func.count()).select_from(SourceFile).where(*conds)) or 0
    rows = db.scalars(select(SourceFile).where(*conds)
                      .order_by(SourceFile.change_count.desc(), SourceFile.path)
                      .offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [
        {"id": f.id, "path": f.path, "module_name": f.module_name,
         "language": f.language, "one_liner": f.one_liner,
         "evolution_line": f.evolution_line, "risk_level": f.risk_level,
         "change_count": f.change_count, "last_commit_sha": f.last_commit_sha,
         "updated_at": f.updated_at.isoformat() if f.updated_at else None}
        for f in rows]}


@router.get("/files/{file_id}")
def file_detail(file_id: int, branch: str = "", risk: str = "", author: str = "",
                db: Session = Depends(get_db)):
    f = db.get(SourceFile, file_id)
    if not f:
        raise HTTPException(404, "文件档案不存在")
    cfg = llm_service.get_config(db)
    conds = [FileChangeEvent.source_file_id == file_id]
    if branch:
        conds.append(FileChangeEvent.branch == branch)
    if risk:
        conds.append(FileChangeEvent.risk_level == risk)
    if author:
        conds.append(FileChangeEvent.author.contains(author))
    events = db.scalars(select(FileChangeEvent).where(*conds)
                        .order_by(FileChangeEvent.committed_at.desc().nullslast(),
                                  FileChangeEvent.id.desc())).all()
    branches = db.scalars(select(FileChangeEvent.branch)
                          .where(FileChangeEvent.source_file_id == file_id).distinct()).all()
    base = (cfg.commit_web_base_url or "").strip().rstrip("/")
    return {
        "file": {"id": f.id, "path": f.path, "module_name": f.module_name,
                 "language": f.language, "one_liner": f.one_liner,
                 "current_doc": f.current_doc, "evolution_line": f.evolution_line,
                 "risk_level": f.risk_level, "change_count": f.change_count,
                 "baseline_doc_path": f.baseline_doc_path},
        "commit_base": base,
        "branches": [b for b in branches if b],
        "events": [{
            "id": e.id, "commit_sha": e.commit_sha, "sha_short": e.commit_sha[:7],
            "branch": e.branch, "author": e.author,
            "committed_at": e.committed_at.isoformat() if e.committed_at else "",
            "commit_message": e.commit_message, "summary": e.summary,
            "blocks": e.blocks or [], "doc_update": e.doc_update,
            "motivation": e.motivation, "evidence_source": e.evidence_source,
            "risk_level": e.risk_level, "diff_stats": e.diff_stats or {},
            "analysis_mode": e.analysis_mode,
        } for e in events],
    }


@router.get("/files/{file_id}/doc")
def file_doc(file_id: int, db: Session = Depends(get_db)):
    f = db.get(SourceFile, file_id)
    if not f:
        raise HTTPException(404, "文件档案不存在")
    p = Path(f.baseline_doc_path) if f.baseline_doc_path else None
    return {"path": f.path, "doc_md": f.current_doc,
            "disk_path": str(p) if p else "",
            "exists": bool(p and p.exists())}


# ---------------- 提交检索 ----------------

@router.get("/repos/{repo_id}/commits")
def list_commits(repo_id: int, q: str = "", branch: str = "", risk: str = "",
                 author: str = "", file: str = "", only_high: str = "",
                 page: int = 1, size: int = 30, db: Session = Depends(get_db)):
    conds = [CommitAnalysis.repo_id == repo_id]
    if q:
        conds.append(or_(CommitAnalysis.message.contains(q),
                         CommitAnalysis.summary.contains(q),
                         CommitAnalysis.commit_sha.contains(q)))
    if branch:
        conds.append(CommitAnalysis.branch == branch)
    if risk:
        conds.append(CommitAnalysis.risk_level == risk)
    if author:
        conds.append(CommitAnalysis.author.contains(author))
    if only_high == "1":
        conds.append(CommitAnalysis.is_high_signal.is_(True))
    if file:
        sub = (select(FileChangeEvent.commit_sha)
               .join(SourceFile, SourceFile.id == FileChangeEvent.source_file_id)
               .where(SourceFile.repo_id == repo_id, SourceFile.path.contains(file)))
        conds.append(CommitAnalysis.commit_sha.in_(sub))
    total = db.scalar(select(func.count()).select_from(CommitAnalysis).where(*conds)) or 0
    rows = db.scalars(select(CommitAnalysis).where(*conds)
                      .order_by(CommitAnalysis.committed_at.desc().nullslast(),
                                CommitAnalysis.id.desc())
                      .offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [{
        "id": c.id, "commit_sha": c.commit_sha, "sha_short": c.commit_sha[:7],
        "branch": c.branch, "author": c.author,
        "committed_at": c.committed_at.isoformat() if c.committed_at else "",
        "message": c.message, "summary": c.summary, "motivation": c.motivation,
        "evidence_source": c.evidence_source, "affected_files": c.affected_files or [],
        "diff_stats": c.diff_stats or {}, "risk_level": c.risk_level,
        "is_high_signal": c.is_high_signal, "filter_reason": c.filter_reason,
        "analysis_mode": c.analysis_mode,
    } for c in rows]}


@router.get("/repos/{repo_id}/branches")
def list_branch_states(repo_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(BranchState).where(BranchState.repo_id == repo_id)).all()
    return {"items": [{"branch": s.branch, "last_commit_sha": s.last_commit_sha,
                       "updated_at": s.updated_at.isoformat() if s.updated_at else None}
                      for s in rows]}


# ---------------- 需求 / 缺陷追溯 ----------------

LINK_TYPE_CN = {"explicit": "明确引用", "semantic": "语义推测",
                "inferred": "上下文推断", "manual": "人工挂载"}
ASSESS_RANK = {"strong": 3, "review": 2, "weak": 1, "none": 0}


def _link_payload(link: IssueCommitLink, issue: Issue | None = None,
                  ca: CommitAnalysis | None = None) -> dict:
    return {
        "id": link.id, "issue_id": link.issue_id, "repo_id": link.repo_id,
        "commit_sha": link.commit_sha, "sha_short": link.commit_sha[:7],
        "branch": link.branch, "link_type": link.link_type,
        "link_type_cn": LINK_TYPE_CN.get(link.link_type, link.link_type),
        "confidence": link.confidence, "evidence": link.evidence,
        "signals": link.signals or {}, "assessment": link.assessment,
        "assessment_label": link.assessment_label,
        "assessment_note": link.assessment_note, "llm_note": link.llm_note,
        "review_status": link.review_status,
        "issue": ({"id": issue.id, "external_id": issue.external_id,
                   "issue_type": issue.issue_type, "title": issue.title,
                   "external_url": issue.external_url, "status": issue.status}
                  if issue else None),
        "commit": ({"message": ca.message, "author": ca.author,
                    "committed_at": ca.committed_at.isoformat() if ca.committed_at else "",
                    "summary": ca.summary, "affected_files": ca.affected_files or [],
                    "is_high_signal": ca.is_high_signal, "risk_level": ca.risk_level}
                   if ca else None),
    }


def _all_links(db: Session, repo_id: int) -> tuple[list[IssueCommitLink], dict, dict]:
    links = list(db.scalars(select(IssueCommitLink)
                            .where(IssueCommitLink.repo_id == repo_id)).all())
    issues = {i.id: i for i in db.scalars(
        select(Issue).where(Issue.repo_id == repo_id)).all()}
    shas = [l.commit_sha for l in links]
    cas = {c.commit_sha: c for c in db.scalars(
        select(CommitAnalysis).where(CommitAnalysis.commit_sha.in_(shas or ["__none__"]))).all()}
    return links, issues, cas


@router.get("/repos/{repo_id}/issues")
def list_issues(repo_id: int, q: str = "", issue_type: str = "", status: str = "",
                assessment: str = "", db: Session = Depends(get_db)):
    rows = db.scalars(select(Issue).where(Issue.repo_id == repo_id)
                      .order_by(Issue.id.desc())).all()
    links, _, _ = _all_links(db, repo_id)
    grouped: dict[int, list[IssueCommitLink]] = {}
    for l in links:
        grouped.setdefault(l.issue_id, []).append(l)
    items = []
    for it in rows:
        if q and q.lower() not in f"{it.external_id} {it.title} {it.description}".lower():
            continue
        if issue_type and it.issue_type != issue_type:
            continue
        if status and it.status != status:
            continue
        ls = [l for l in grouped.get(it.id, []) if l.review_status != "rejected"]
        active = [l for l in ls if l.review_status == "confirmed"]
        best = "none"
        for l in ls:
            if ASSESS_RANK.get(l.assessment, 0) > ASSESS_RANK.get(best, 0):
                best = l.assessment
        if assessment and best != assessment:
            continue
        items.append({
            "id": it.id, "external_id": it.external_id, "issue_type": it.issue_type,
            "title": it.title, "description": it.description, "status": it.status,
            "source": it.source, "external_url": it.external_url,
            "reporter": it.reporter, "keywords": it.keywords or [],
            "related_paths": it.related_paths or [],
            "occurred_at": it.occurred_at.isoformat() if it.occurred_at else "",
            "link_count": len(ls), "confirmed_count": len(active),
            "pending_count": sum(1 for l in ls if l.review_status == "pending"),
            "strong_count": sum(1 for l in ls if l.assessment == "strong"),
            "review_count": sum(1 for l in ls if l.assessment == "review"),
            "best_assessment": best,
        })
    return {"items": items, "total": len(items)}


@router.post("/repos/{repo_id}/issues")
def create_issue(repo_id: int, payload: IssueCreate, db: Session = Depends(get_db)):
    if not db.get(Repository, repo_id):
        raise HTTPException(404, "仓库不存在")
    try:
        issue, created = issue_linker.upsert_issue(db, repo_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    relink = issue_linker.relink_repo(db, repo_id, use_llm=False, only_new=False)
    return {"ok": True, "id": issue.id, "external_id": issue.external_id,
            "created": created, "new_links": relink["new_links"]}


@router.post("/repos/{repo_id}/issues/import")
def import_issues(repo_id: int, payload: IssueImport, db: Session = Depends(get_db)):
    if not db.get(Repository, repo_id):
        raise HTTPException(404, "仓库不存在")
    try:
        result = issue_linker.import_csv(db, repo_id, payload.csv_text, payload.source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    relink = issue_linker.relink_repo(db, repo_id, use_llm=False, only_new=False)
    return {"ok": True, **result, "new_links": relink["new_links"]}


@router.post("/repos/{repo_id}/relink")
def relink(repo_id: int, payload: dict | None = None, db: Session = Depends(get_db)):
    """手动重跑关联（新增需求后、或补登记相关路径后使用）。"""
    use_llm = bool((payload or {}).get("use_llm"))
    return {"ok": True, **issue_linker.relink_repo(db, repo_id, use_llm=use_llm,
                                                   only_new=False)}


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(404, "需求/缺陷不存在")
    links, issues_map, cas = _all_links(db, issue.repo_id)
    mine = [l for l in links if l.issue_id == issue_id]
    mine.sort(key=lambda l: (l.review_status != "rejected",
                             ASSESS_RANK.get(l.assessment, 0), l.confidence), reverse=True)
    cfg = llm_service.get_config(db)
    paths: set[str] = set()
    for l in mine:
        c = cas.get(l.commit_sha)
        if c:
            paths.update(c.affected_files or [])
    sfs = list(db.scalars(select(SourceFile).where(
        SourceFile.repo_id == issue.repo_id,
        SourceFile.path.in_(list(paths) or ["__none__"]))).all())
    modules = sorted({f.module_name for f in sfs if f.module_name})
    return {
        "issue": {"id": issue.id, "repo_id": issue.repo_id,
                  "external_id": issue.external_id, "issue_type": issue.issue_type,
                  "title": issue.title, "description": issue.description,
                  "status": issue.status, "source": issue.source,
                  "external_url": issue.external_url, "reporter": issue.reporter,
                  "keywords": issue.keywords or [], "related_paths": issue.related_paths or [],
                  "occurred_at": issue.occurred_at.isoformat() if issue.occurred_at else ""},
        "commit_base": (cfg.commit_web_base_url or "").strip().rstrip("/"),
        "links": [_link_payload(l, issues_map.get(l.issue_id), cas.get(l.commit_sha)) for l in mine],
        "files": [{"id": f.id, "path": f.path, "module_name": f.module_name}
                  for f in sfs[:40]],
        "modules": modules,
        "summary": {
            "total": len(mine),
            "confirmed": sum(1 for l in mine if l.review_status == "confirmed"),
            "pending": sum(1 for l in mine if l.review_status == "pending"),
            "rejected": sum(1 for l in mine if l.review_status == "rejected"),
            "strong": sum(1 for l in mine if l.assessment == "strong"),
            "review": sum(1 for l in mine if l.assessment == "review"),
        },
    }


@router.put("/issues/{issue_id}")
def update_issue(issue_id: int, payload: dict, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(404, "需求/缺陷不存在")
    data = {k: v for k, v in payload.items() if k != "external_id"}
    data["external_id"] = issue.external_id
    try:
        issue_linker.upsert_issue(db, issue.repo_id, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    return {"ok": True, "id": issue_id}


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(404, "需求/缺陷不存在")
    db.query(IssueCommitLink).filter(IssueCommitLink.issue_id == issue_id).delete()
    db.delete(issue)
    db.commit()
    return {"ok": True}


@router.post("/issue-links/{link_id}/confirm")
def confirm_link(link_id: int, db: Session = Depends(get_db)):
    try:
        return issue_linker.review_link(db, link_id, "confirm")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/issue-links/{link_id}/reject")
def reject_link(link_id: int, db: Session = Depends(get_db)):
    try:
        return issue_linker.review_link(db, link_id, "reject")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/repos/{repo_id}/issue-links")
def list_issue_links(repo_id: int, db: Session = Depends(get_db)):
    """按提交 SHA 分组，供文件/模块/提交页反向展示「关联需求」。"""
    links, issues, cas = _all_links(db, repo_id)
    out: dict[str, list[dict]] = {}
    for l in links:
        if l.review_status == "rejected":
            continue
        out.setdefault(l.commit_sha, []).append(
            _link_payload(l, issues.get(l.issue_id), cas.get(l.commit_sha)))
    return {"by_sha": out, "total": len(links)}
