"""分析产物数据访问层：模块 / 文件 / 提交 / 需求缺陷 / 分支。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError
from ..models.knowledge import (
    BranchState, CommitAnalysis, FileChangeEvent, Issue,
    IssueCommitLink, ModuleCandidate, ModuleChangeEvent, ProjectModule, SourceFile,
)


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


# ============ 模块 ============
def list_modules(db: Session, repo_id: int) -> list[dict]:
    items = db.scalars(
        select(ProjectModule).where(ProjectModule.repo_id == repo_id).order_by(ProjectModule.id)
    ).all()
    return [{
        "id": m.id, "name": m.name, "path_rules": m.path_rules or [],
        "responsibility": m.responsibility, "one_liner": m.one_liner,
        "evolution_line": m.evolution_line, "status": m.status,
        "change_count": m.change_count, "file_count": m.file_count,
        "doc_path": m.doc_path,
    } for m in items]


def get_module(db: Session, module_id: int) -> ProjectModule | None:
    return db.get(ProjectModule, module_id)


def module_detail(db: Session, module_id: int, branch: str = "") -> dict:
    m = db.get(ProjectModule, module_id)
    if not m:
        raise NotFoundError("模块")
    conds = [ModuleChangeEvent.module_id == module_id]
    if branch:
        conds.append(ModuleChangeEvent.branch == branch)
    events = db.scalars(
        select(ModuleChangeEvent).where(*conds)
        .order_by(ModuleChangeEvent.committed_at.desc().nullslast(), ModuleChangeEvent.id.desc())
    ).all()
    files = db.scalars(
        select(SourceFile).where(SourceFile.repo_id == m.repo_id, SourceFile.module_name == m.name)
        .order_by(SourceFile.change_count.desc(), SourceFile.path)
    ).all()
    branches = [b for b in db.scalars(
        select(ModuleChangeEvent.branch).where(ModuleChangeEvent.module_id == module_id).distinct()
    ).all() if b]
    return {
        "module": {
            "id": m.id, "name": m.name, "repo_id": m.repo_id,
            "path_rules": m.path_rules or [], "responsibility": m.responsibility,
            "one_liner": m.one_liner, "current_doc": m.current_doc,
            "evolution_line": m.evolution_line, "status": m.status,
            "change_count": m.change_count, "file_count": m.file_count,
            "doc_path": m.doc_path, "last_commit_sha": m.last_commit_sha,
        },
        "branches": branches,
        "files": [{"id": f.id, "path": f.path, "one_liner": f.one_liner,
                   "change_count": f.change_count, "risk_level": f.risk_level} for f in files],
        "events": [{
            "id": e.id, "commit_sha": e.commit_sha, "sha_short": e.commit_sha[:7],
            "branch": e.branch, "author": e.author, "committed_at": _iso(e.committed_at),
            "commit_message": e.commit_message, "summary": e.summary,
            "capability_delta": e.capability_delta, "affected_files": e.affected_files or [],
            "motivation": e.motivation, "evidence_source": e.evidence_source,
            "risk_level": e.risk_level, "analysis_mode": e.analysis_mode,
        } for e in events],
    }


def list_module_candidates(db: Session, repo_id: int) -> list[dict]:
    rows = db.scalars(
        select(ModuleCandidate).where(ModuleCandidate.repo_id == repo_id)
        .order_by(ModuleCandidate.id.desc())
    ).all()
    return [{
        "id": c.id, "name": c.name, "path_rules": c.path_rules or [], "reason": c.reason,
        "evidence_commit": c.evidence_commit, "sample_files": c.sample_files or [],
        "status": c.status, "created_at": _iso(c.created_at),
    } for c in rows]


# ============ 文件 ============
def list_files(db: Session, repo_id: int, q: str = "", module: str = "", risk: str = "",
               page: int = 1, size: int = 30) -> dict:
    conds = [SourceFile.repo_id == repo_id]
    if q:
        conds.append(or_(SourceFile.path.contains(q), SourceFile.one_liner.contains(q)))
    if module:
        conds.append(SourceFile.module_name == module)
    if risk:
        conds.append(SourceFile.risk_level == risk)
    total = db.scalar(select(func.count()).select_from(SourceFile).where(*conds)) or 0
    rows = db.scalars(
        select(SourceFile).where(*conds)
        .order_by(SourceFile.change_count.desc(), SourceFile.path)
        .offset((page - 1) * size).limit(size)
    ).all()
    return {"total": total, "page": page, "size": size, "items": [{
        "id": f.id, "path": f.path, "module_name": f.module_name, "language": f.language,
        "one_liner": f.one_liner, "evolution_line": f.evolution_line,
        "risk_level": f.risk_level, "change_count": f.change_count,
        "last_commit_sha": f.last_commit_sha, "updated_at": _iso(f.updated_at),
    } for f in rows]}


def get_file(db: Session, file_id: int) -> SourceFile | None:
    return db.get(SourceFile, file_id)


def file_detail(db: Session, file_id: int, branch: str = "", risk: str = "", author: str = "") -> dict:
    f = db.get(SourceFile, file_id)
    if not f:
        raise NotFoundError("文件档案")
    conds = [FileChangeEvent.source_file_id == file_id]
    if branch:
        conds.append(FileChangeEvent.branch == branch)
    if risk:
        conds.append(FileChangeEvent.risk_level == risk)
    if author:
        conds.append(FileChangeEvent.author.contains(author))
    events = db.scalars(
        select(FileChangeEvent).where(*conds)
        .order_by(FileChangeEvent.committed_at.desc().nullslast(), FileChangeEvent.id.desc())
    ).all()
    branches = db.scalars(
        select(FileChangeEvent.branch).where(FileChangeEvent.source_file_id == file_id).distinct()
    ).all()
    return {
        "file": {
            "id": f.id, "path": f.path, "module_name": f.module_name, "language": f.language,
            "one_liner": f.one_liner, "current_doc": f.current_doc,
            "evolution_line": f.evolution_line, "risk_level": f.risk_level,
            "change_count": f.change_count, "baseline_doc_path": f.baseline_doc_path,
        },
        "branches": [b for b in branches if b],
        "events": [{
            "id": e.id, "commit_sha": e.commit_sha, "sha_short": e.commit_sha[:7],
            "branch": e.branch, "author": e.author, "committed_at": _iso(e.committed_at),
            "commit_message": e.commit_message, "summary": e.summary,
            "blocks": e.blocks or [], "doc_update": e.doc_update,
            "motivation": e.motivation, "evidence_source": e.evidence_source,
            "risk_level": e.risk_level, "diff_stats": e.diff_stats or {},
            "analysis_mode": e.analysis_mode,
        } for e in events],
    }


def file_doc(db: Session, file_id: int) -> dict:
    from pathlib import Path
    f = db.get(SourceFile, file_id)
    if not f:
        raise NotFoundError("文件档案")
    p = Path(f.baseline_doc_path) if f.baseline_doc_path else None
    return {"path": f.path, "doc_md": f.current_doc,
            "disk_path": str(p) if p else "", "exists": bool(p and p.exists())}


# ============ 提交 ============
def list_commits(db: Session, repo_id: int, q: str = "", branch: str = "", risk: str = "",
                 author: str = "", file: str = "", only_high: bool = False,
                 page: int = 1, size: int = 30, user_id: int | None = None) -> dict:
    conds = [CommitAnalysis.repo_id == repo_id]
    if user_id:
        from ..repositories.git_identity_repo import emails_for_users, names_for_users
        emails, names = emails_for_users(db, [user_id]), names_for_users(db, [user_id])
        parts = [CommitAnalysis.author_email.in_(emails)] if emails else []
        parts += [CommitAnalysis.author.in_(names)] if names else []
        conds.append(or_(*parts) if parts else CommitAnalysis.id < 0)
    if q:
        conds.append(or_(CommitAnalysis.message.contains(q), CommitAnalysis.summary.contains(q),
                         CommitAnalysis.commit_sha.contains(q)))
    if branch:
        conds.append(CommitAnalysis.branch == branch)
    if risk:
        conds.append(CommitAnalysis.risk_level == risk)
    if author:
        conds.append(CommitAnalysis.author.contains(author))
    if only_high:
        conds.append(CommitAnalysis.is_high_signal.is_(True))
    if file:
        sub = (select(FileChangeEvent.commit_sha)
               .join(SourceFile, SourceFile.id == FileChangeEvent.source_file_id)
               .where(SourceFile.repo_id == repo_id, SourceFile.path.contains(file)))
        conds.append(CommitAnalysis.commit_sha.in_(sub))
    total = db.scalar(select(func.count()).select_from(CommitAnalysis).where(*conds)) or 0
    rows = db.scalars(
        select(CommitAnalysis).where(*conds)
        .order_by(CommitAnalysis.committed_at.desc().nullslast(), CommitAnalysis.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return {"total": total, "page": page, "size": size, "items": [{
        "id": c.id, "commit_sha": c.commit_sha, "sha_short": c.commit_sha[:7],
        "branch": c.branch, "author": c.author,
        "author_email": getattr(c, "author_email", ""), "committed_at": _iso(c.committed_at),
        "message": c.message, "summary": c.summary, "motivation": c.motivation,
        "evidence_source": c.evidence_source, "affected_files": c.affected_files or [],
        "diff_stats": c.diff_stats or {}, "risk_level": c.risk_level,
        "is_high_signal": c.is_high_signal, "filter_reason": c.filter_reason,
        "analysis_mode": c.analysis_mode,
    } for c in rows]}


def list_branches(db: Session, repo_id: int) -> list[dict]:
    rows = db.scalars(select(BranchState).where(BranchState.repo_id == repo_id)).all()
    return [{"branch": s.branch, "last_commit_sha": s.last_commit_sha,
             "updated_at": _iso(s.updated_at)} for s in rows]


# ============ 需求缺陷 ============
LINK_TYPE_CN = {"explicit": "明确引用", "semantic": "语义推测",
                "inferred": "上下文推断", "manual": "人工挂载"}
ASSESS_RANK = {"strong": 3, "review": 2, "weak": 1, "none": 0}


def link_payload(link: IssueCommitLink, issue: Issue | None = None,
                  ca: CommitAnalysis | None = None) -> dict:
    return {
        "id": link.id, "issue_id": link.issue_id, "commit_sha": link.commit_sha,
        "sha_short": link.commit_sha[:7], "branch": link.branch,
        "link_type": link.link_type, "link_type_cn": LINK_TYPE_CN.get(link.link_type, link.link_type),
        "confidence": link.confidence, "evidence": link.evidence,
        "signals": link.signals or {}, "assessment": link.assessment,
        "assessment_label": link.assessment_label, "assessment_note": link.assessment_note,
        "review_status": link.review_status, "llm_note": link.llm_note,
        "issue": ({"id": issue.id, "external_id": issue.external_id, "title": issue.title,
                   "issue_type": issue.issue_type, "status": issue.status} if issue else None),
        "commit": ({"message": ca.message, "author": ca.author,
                    "committed_at": _iso(ca.committed_at)} if ca else None),
    }


def list_issues(db: Session, repo_id: int, q: str = "", issue_type: str = "",
                status: str = "", assessment: str = "") -> list[dict]:
    conds = [Issue.repo_id == repo_id]
    if q:
        conds.append(or_(Issue.external_id.contains(q), Issue.title.contains(q),
                         Issue.description.contains(q)))
    if issue_type:
        conds.append(Issue.issue_type == issue_type)
    if status:
        conds.append(Issue.status == status)
    rows = db.scalars(select(Issue).where(*conds).order_by(Issue.id.desc())).all()
    out = []
    for iss in rows:
        links = db.scalars(select(IssueCommitLink).where(IssueCommitLink.issue_id == iss.id)).all()
        best = max((l.assessment for l in links), key=lambda a: ASSESS_RANK.get(a, 0), default="none")
        if assessment and assessment != best:
            continue
        out.append({
            "id": iss.id, "external_id": iss.external_id, "issue_type": iss.issue_type,
            "title": iss.title, "status": iss.status, "source": iss.source,
            "reporter": iss.reporter, "related_paths": iss.related_paths or [],
            "link_count": len(links), "best_assessment": best,
            "created_at": _iso(iss.created_at), "updated_at": _iso(iss.updated_at),
        })
    return out


def get_issue(db: Session, issue_id: int) -> Issue | None:
    return db.get(Issue, issue_id)


def issue_detail(db: Session, issue_id: int) -> dict:
    iss = db.get(Issue, issue_id)
    if not iss:
        raise NotFoundError("事项")
    links = db.scalars(
        select(IssueCommitLink).where(IssueCommitLink.issue_id == issue_id)
        .order_by(IssueCommitLink.id.desc())
    ).all()
    payloads = []
    for l in links:
        ca = db.scalar(select(CommitAnalysis).where(
            CommitAnalysis.commit_sha == l.commit_sha, CommitAnalysis.repo_id == iss.repo_id))
        payloads.append(link_payload(l, iss, ca))
    confirmed = sum(1 for l in links if l.review_status == "confirmed")
    pending = sum(1 for l in links if l.review_status == "pending")
    return {
        "issue": {
            "id": iss.id, "external_id": iss.external_id, "issue_type": iss.issue_type,
            "title": iss.title, "description": iss.description, "status": iss.status,
            "source": iss.source, "external_url": iss.external_url, "reporter": iss.reporter,
            "keywords": iss.keywords or [], "related_paths": iss.related_paths or [],
            "occurred_at": _iso(iss.occurred_at), "created_at": _iso(iss.created_at),
        },
        "links": payloads,
        "stats": {"link_count": len(links), "confirmed": confirmed, "pending": pending},
    }


def get_link(db: Session, link_id: int) -> IssueCommitLink | None:
    return db.get(IssueCommitLink, link_id)


def issue_links_by_commit(db: Session, repo_id: int) -> dict:
    links = db.scalars(
        select(IssueCommitLink).where(
            IssueCommitLink.repo_id == repo_id, IssueCommitLink.review_status != "rejected")
    ).all()
    grouped: dict[str, list[dict]] = {}
    for l in links:
        iss = db.get(Issue, l.issue_id)
        grouped.setdefault(l.commit_sha, []).append(link_payload(l, iss, None))
    return grouped
