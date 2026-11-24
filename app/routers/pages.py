"""Web 页面路由：概览 / 模块 / 文件 / 提交 / 需求缺陷追溯 / 系统设置。"""
from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import issue_linker, llm_service
from ..database import SessionLocal
from . import api as api_views
from ..models import (BranchState, CommitAnalysis, FileChangeEvent, Issue, IssueCommitLink,
                      ModuleCandidate, ModuleChangeEvent, ProjectModule, Repository,
                      SourceFile)

router = APIRouter(tags=["pages"])


def _render(request: Request, name: str, ctx: dict):
    # Starlette >= 0.4x 要求显式传入 request 作为第一个参数
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def _md_to_html(text: str) -> str:
    """轻量 Markdown 渲染（服务端兜底，离线可用；前端 Marked.js 会二次增强）。"""
    if not text:
        return "<p class='muted'>暂无说明</p>"
    out: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            out.append("<pre><code>" if not in_code else "</code></pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line) + "\n")
            continue
        esc = html.escape(line)
        esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
        esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
        if line.startswith("### "):
            out.append(f"<h4>{esc[4:]}</h4>")
        elif line.startswith("## "):
            out.append(f"<h3>{esc[3:]}</h3>")
        elif line.startswith("# "):
            out.append(f"<h2>{esc[2:]}</h2>")
        elif re.match(r"^\s*[-*]\s+", line):
            out.append(f"<div class='md-li'>{esc}</div>")
        elif line.strip() == "":
            out.append("<div class='md-gap'></div>")
        else:
            out.append(f"<p>{esc}</p>")
    if in_code:
        out.append("</code></pre>")
    return "".join(out)


def _context(request: Request, db: Session, active: str = "", rid: int = 0) -> dict:
    repos = db.scalars(select(Repository).order_by(Repository.id.desc())).all()
    if not rid:
        try:
            rid = int(request.query_params.get("repo_id") or 0)
        except ValueError:
            rid = 0
    if not rid and repos:
        rid = repos[0].id
    active_repo = next((r for r in repos if r.id == rid), None)
    cfg = llm_service.get_config(db)
    return {
        "request": request, "active": active, "repos": repos, "rid": rid,
        "active_repo": active_repo, "cfg": cfg,
        "llm_mode": "LLM" if (cfg.llm_enabled and cfg.api_key) else "本地规则",
        "commit_base": (cfg.commit_web_base_url or "").strip().rstrip("/"),
    }


def _stats(db: Session, repo_id: int) -> dict:
    def c(model, *conds):
        q = select(func.count()).select_from(model)
        if repo_id:
            q = q.where(model.repo_id == repo_id)
        for x in conds:
            q = q.where(x)
        return db.scalar(q) or 0
    return {"repos": c(Repository) if not repo_id else 1,
            "modules": c(ProjectModule), "files": c(SourceFile),
            "events": c(FileChangeEvent), "commits": c(CommitAnalysis),
            "filtered": c(CommitAnalysis, CommitAnalysis.is_high_signal.is_(False)),
            "branches": c(BranchState),
            "risky": c(SourceFile, SourceFile.risk_level == "高"),
            "issues": c(Issue), "issue_links": c(IssueCommitLink),
            "pending_issue_reviews": c(IssueCommitLink,
                                       IssueCommitLink.review_status == "pending")}


def _issue_links_for(db: Session, repo_id: int, shas: list[str]) -> tuple[dict, list[dict]]:
    """按提交 SHA 分组的关联需求，以及去重后的需求清单（供文件/模块/提交页反向跳转）。"""
    uniq = list(dict.fromkeys(s for s in shas if s))
    if not repo_id or not uniq:
        return {}, []
    links = db.scalars(select(IssueCommitLink).where(
        IssueCommitLink.repo_id == repo_id,
        IssueCommitLink.commit_sha.in_(uniq),
        IssueCommitLink.review_status != "rejected")).all()
    issues = {i.id: i for i in db.scalars(
        select(Issue).where(Issue.repo_id == repo_id)).all()}
    by_sha: dict[str, list[dict]] = {}
    refs: dict[int, dict] = {}
    cn = {"explicit": "明确引用", "semantic": "语义推测",
          "inferred": "上下文推断", "manual": "人工挂载"}
    for l in links:
        it = issues.get(l.issue_id)
        if not it:
            continue
        item = {"id": l.id, "issue_id": it.id, "external_id": it.external_id,
                "title": it.title, "issue_type": it.issue_type,
                "link_type": l.link_type, "link_type_cn": cn.get(l.link_type, l.link_type),
                "confidence": l.confidence, "assessment": l.assessment,
                "assessment_label": l.assessment_label,
                "review_status": l.review_status}
        by_sha.setdefault(l.commit_sha, []).append(item)
        refs[it.id] = {"id": it.id, "external_id": it.external_id,
                       "title": it.title, "issue_type": it.issue_type,
                       "status": it.status, "best": l.assessment,
                       "best_label": l.assessment_label}
    return by_sha, list(refs.values())


@router.get("/", response_class=HTMLResponse)
def page_index(request: Request):
    with SessionLocal() as db:
        ctx = _context(request, db, "index")
        ctx["stats"] = _stats(db, ctx["rid"])
        repo_rows = []
        for r in ctx["repos"]:
            repo_rows.append({
                "id": r.id, "name": r.name, "source": r.source,
                "source_type": r.source_type, "status": r.status,
                "status_message": r.status_message,
                "branches": r.branches or [],
                "last_analyzed_at": r.last_analyzed_at.strftime("%Y-%m-%d %H:%M") if r.last_analyzed_at else "—",
                "files": db.scalar(select(func.count()).select_from(SourceFile)
                                   .where(SourceFile.repo_id == r.id)) or 0,
                "commits": db.scalar(select(func.count()).select_from(CommitAnalysis)
                                     .where(CommitAnalysis.repo_id == r.id,
                                            CommitAnalysis.is_high_signal.is_(True))) or 0,
            })
        ctx["repo_rows"] = repo_rows
        ctx["recent_events"] = db.scalars(
            select(FileChangeEvent).where(FileChangeEvent.repo_id == ctx["rid"])
            .order_by(FileChangeEvent.committed_at.desc().nullslast(), FileChangeEvent.id.desc())
            .limit(8)).all() if ctx["rid"] else []
        ctx["recent_issues"] = db.scalars(
            select(Issue).where(Issue.repo_id == ctx["rid"])
            .order_by(Issue.id.desc()).limit(5)).all() if ctx["rid"] else []
        return _render(request, "index.html", ctx)


@router.get("/modules", response_class=HTMLResponse)
def page_modules(request: Request):
    with SessionLocal() as db:
        ctx = _context(request, db, "modules")
        ctx["modules"] = db.scalars(select(ProjectModule)
                                    .where(ProjectModule.repo_id == ctx["rid"])
                                    .order_by(ProjectModule.id)).all() if ctx["rid"] else []
        ctx["candidates"] = db.scalars(select(ModuleCandidate)
                                       .where(ModuleCandidate.repo_id == ctx["rid"],
                                              ModuleCandidate.status == "pending")
                                       .order_by(ModuleCandidate.id.desc())).all() if ctx["rid"] else []
        return _render(request, "modules.html", ctx)


@router.get("/modules/{module_id}", response_class=HTMLResponse)
def page_module_detail(request: Request, module_id: int, branch: str = ""):
    with SessionLocal() as db:
        ctx = _context(request, db, "modules")
        m = db.get(ProjectModule, module_id)
        if not m:
            return HTMLResponse("<h2>模块不存在</h2><a href='/modules'>返回模块清单</a>",
                                status_code=404)
        conds = [ModuleChangeEvent.module_id == module_id]
        if branch:
            conds.append(ModuleChangeEvent.branch == branch)
        events = db.scalars(select(ModuleChangeEvent).where(*conds)
                            .order_by(ModuleChangeEvent.committed_at.desc().nullslast(),
                                      ModuleChangeEvent.id.desc())).all()
        branches = [b for b in db.scalars(select(ModuleChangeEvent.branch)
                                          .where(ModuleChangeEvent.module_id == module_id)
                                          .distinct()).all() if b]
        files = db.scalars(select(SourceFile).where(SourceFile.repo_id == m.repo_id,
                                                    SourceFile.module_name == m.name)
                           .order_by(SourceFile.change_count.desc(), SourceFile.path)).all()
        cfg = llm_service.get_config(db)
        issue_by_sha, related_issues = _issue_links_for(
            db, m.repo_id, [e.commit_sha for e in events])
        ctx.update({"m": m, "events": events, "branches": branches, "branch": branch,
                    "module_files": files, "doc_html": _md_to_html(m.current_doc),
                    "commit_base": (cfg.commit_web_base_url or "").strip().rstrip("/"),
                    "doc_disk_exists": bool(m.doc_path and Path(m.doc_path).exists()),
                    "issue_by_sha": issue_by_sha, "related_issues": related_issues})
        return _render(request, "module_detail.html", ctx)


@router.get("/files", response_class=HTMLResponse)
def page_files(request: Request, q: str = "", module: str = "", risk: str = "", page: int = 1):
    with SessionLocal() as db:
        ctx = _context(request, db, "files")
        conds = [SourceFile.repo_id == ctx["rid"]]
        if q:
            conds.append(or_(SourceFile.path.contains(q), SourceFile.one_liner.contains(q)))
        if module:
            conds.append(SourceFile.module_name == module)
        if risk:
            conds.append(SourceFile.risk_level == risk)
        size = 30
        total = db.scalar(select(func.count()).select_from(SourceFile).where(*conds)) or 0
        rows = db.scalars(select(SourceFile).where(*conds)
                          .order_by(SourceFile.change_count.desc(), SourceFile.path)
                          .offset((page - 1) * size).limit(size)).all() if ctx["rid"] else []
        ctx.update({"files": rows, "total": total, "page": page,
                    "pages": max(1, (total + size - 1) // size),
                    "q": q, "module": module, "risk": risk,
                    "modules": db.scalars(select(ProjectModule)
                                          .where(ProjectModule.repo_id == ctx["rid"])).all()
                    if ctx["rid"] else []})
        return _render(request, "files.html", ctx)


@router.get("/files/{file_id}", response_class=HTMLResponse)
def page_file_detail(request: Request, file_id: int, branch: str = "", risk: str = "",
                     author: str = ""):
    with SessionLocal() as db:
        ctx = _context(request, db, "files")
        f = db.get(SourceFile, file_id)
        if not f:
            return HTMLResponse("<h2>文件档案不存在</h2><a href='/files'>返回</a>", status_code=404)
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
        branches = [b for b in db.scalars(select(FileChangeEvent.branch)
                                          .where(FileChangeEvent.source_file_id == file_id)
                                          .distinct()).all() if b]
        issue_by_sha, related_issues = _issue_links_for(
            db, f.repo_id, [e.commit_sha for e in events])
        ctx.update({"f": f, "events": events, "branches": branches,
                    "branch": branch, "risk": risk, "author": author,
                    "doc_html": _md_to_html(f.current_doc),
                    "doc_disk_exists": bool(f.baseline_doc_path and Path(f.baseline_doc_path).exists()),
                    "issue_by_sha": issue_by_sha, "related_issues": related_issues})
        return _render(request, "file_detail.html", ctx)


@router.get("/commits", response_class=HTMLResponse)
def page_commits(request: Request, q: str = "", branch: str = "", risk: str = "",
                 author: str = "", file: str = "", only_high: str = "", page: int = 1):
    with SessionLocal() as db:
        ctx = _context(request, db, "commits")
        conds = [CommitAnalysis.repo_id == ctx["rid"]]
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
                   .where(SourceFile.repo_id == ctx["rid"], SourceFile.path.contains(file)))
            conds.append(CommitAnalysis.commit_sha.in_(sub))
        size = 30
        total = db.scalar(select(func.count()).select_from(CommitAnalysis).where(*conds)) or 0
        rows = db.scalars(select(CommitAnalysis).where(*conds)
                          .order_by(CommitAnalysis.committed_at.desc().nullslast(),
                                    CommitAnalysis.id.desc())
                          .offset((page - 1) * size).limit(size)).all() if ctx["rid"] else []
        branch_names = [b for b in db.scalars(select(CommitAnalysis.branch)
                                              .where(CommitAnalysis.repo_id == ctx["rid"])
                                              .distinct()).all() if b]
        issue_by_sha, _ = _issue_links_for(db, ctx["rid"], [c.commit_sha for c in rows])
        ctx.update({"commits": rows, "total": total, "page": page,
                    "pages": max(1, (total + size - 1) // size),
                    "q": q, "branch": branch, "risk": risk, "author": author,
                    "file": file, "only_high": only_high, "branch_names": branch_names,
                    "issue_by_sha": issue_by_sha})
        return _render(request, "commits.html", ctx)


@router.get("/issues", response_class=HTMLResponse)
def page_issues(request: Request, q: str = "", issue_type: str = "",
                status: str = "", assessment: str = ""):
    with SessionLocal() as db:
        ctx = _context(request, db, "issues")
        all_items = (api_views.list_issues(ctx["rid"], db=db)["items"]
                     if ctx["rid"] else [])
        items = (api_views.list_issues(ctx["rid"], q=q, issue_type=issue_type,
                                       status=status, assessment=assessment,
                                       db=db)["items"] if ctx["rid"] else [])
        ctx.update({
            "issues": items, "total": len(items),
            "q": q, "issue_type": issue_type, "status": status,
            "assessment": assessment, "all_count": len(all_items),
            "cnt_strong": sum(1 for x in all_items if x["best_assessment"] == "strong"),
            "cnt_review": sum(1 for x in all_items if x["best_assessment"] == "review"),
            "pending_reviews": sum(x["pending_count"] for x in all_items),
            "csv_sample": (
                "external_id,issue_type,title,description,status,external_url,related_paths,occurred_at\n"
                "#101,bug,重复回调导致重复退款,退款接口被重复调用时二次扣款,resolved,,src/order/refund.py,2026-08-10\n"
                "#102,story,退款改为异步处理,投递 MQ 后轮询状态,closed,,src/order/refund.py,2026-04-28"),
        })
        return _render(request, "issues.html", ctx)


@router.get("/issues/{issue_id}", response_class=HTMLResponse)
def page_issue_detail(request: Request, issue_id: int):
    with SessionLocal() as db:
        try:
            detail = api_views.issue_detail(issue_id, db)
        except HTTPException:
            return HTMLResponse("<h2>需求/缺陷不存在</h2><a href='/issues'>返回需求追溯</a>",
                                status_code=404)
        # 以需求所属仓库为准，保证侧边栏与跳转一致
        ctx = _context(request, db, "issues", rid=detail["issue"]["repo_id"])
        ctx.update(detail)
        module_rows = db.scalars(select(ProjectModule).where(
            ProjectModule.repo_id == detail["issue"]["repo_id"],
            ProjectModule.name.in_(detail["modules"] or ["__none__"]))).all()
        ctx["module_links"] = [{"id": m.id, "name": m.name} for m in module_rows]
        ctx["signal_labels"] = issue_linker.SIGNAL_LABELS
        ctx["doc_html"] = _md_to_html(detail["issue"]["description"])
        return _render(request, "issue_detail.html", ctx)


@router.get("/settings", response_class=HTMLResponse)
def page_settings(request: Request):
    with SessionLocal() as db:
        ctx = _context(request, db, "settings")
        return _render(request, "settings.html", ctx)
