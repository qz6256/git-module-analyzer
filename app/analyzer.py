"""核心分析流水线：全量初始化建档 + 按分支增量同步 + 后台任务管理。"""
from __future__ import annotations

import hashlib
import re
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import diff_parser, git_service, issue_linker, llm_service, signal_filter
from .database import REPOS_DIR, SessionLocal
from .models import (BranchState, CommitAnalysis, FileChangeEvent, Issue, ModuleCandidate,
                     ModuleChangeEvent, ProjectModule, Repository, SourceFile,
                     SystemConfig)

ProgressCB = Callable[[int, str], None]

# ---------------------------------------------------------------------------
# 后台任务管理（内存态，单机够用）
# ---------------------------------------------------------------------------

class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, repo_id: int) -> str:
        jid = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[jid] = {"id": jid, "kind": kind, "repo_id": repo_id,
                               "status": "running", "progress": 0, "message": "任务已排队",
                               "logs": [], "result": {}, "started_at": datetime.now().isoformat()}
        return jid

    def update(self, jid: str, progress: int, message: str) -> None:
        with self._lock:
            j = self._jobs.get(jid)
            if j:
                j["progress"] = progress
                j["message"] = message
                j["logs"].append(f"[{datetime.now():%H:%M:%S}] {message}")
                j["logs"] = j["logs"][-60:]

    def finish(self, jid: str, result: dict, error: str = "") -> None:
        with self._lock:
            j = self._jobs.get(jid)
            if j:
                j["status"] = "error" if error else "done"
                j["progress"] = 100
                j["message"] = error or "任务完成"
                j["result"] = result
                if error:
                    j["logs"].append(f"[错误] {error}")

    def get(self, jid: str) -> dict | None:
        with self._lock:
            j = self._jobs.get(jid)
            return dict(j) if j else None

    def start(self, jid: str, kind: str, repo_id: int, **kwargs) -> None:
        def runner():
            cb = lambda p, m: self.update(jid, p, m)  # noqa: E731
            try:
                with SessionLocal() as db:
                    if kind == "initialize":
                        result = initialize(db, repo_id, cb, **kwargs)
                    else:
                        result = incremental_sync(db, repo_id, cb, **kwargs)
                self.finish(jid, result)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self.finish(jid, {}, error=f"{type(exc).__name__}: {exc}")
                with SessionLocal() as db:
                    repo = db.get(Repository, repo_id)
                    if repo:
                        repo.status = "error"
                        repo.status_message = str(exc)[:300]
                        db.commit()
        threading.Thread(target=runner, daemon=True).start()


jobs = JobManager()


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _repo_dirs(repo_id: int) -> tuple[Path, Path, Path]:
    base = REPOS_DIR / str(repo_id)
    files_dir, modules_dir = base / "files", base / "modules"
    files_dir.mkdir(parents=True, exist_ok=True)
    modules_dir.mkdir(parents=True, exist_ok=True)
    return base, files_dir, modules_dir


def _safe_name(path: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", path.replace("/", "__").replace("\\", "__"))
    digest = hashlib.md5(path.encode("utf-8")).hexdigest()[:8]
    return f"{stem[:90]}_{digest}.md"


def _write_md(directory: Path, path: str, content: str) -> str:
    target = directory / _safe_name(path)
    target.write_text(content or "", encoding="utf-8")
    return str(target)


def _match_module(path: str, modules: list[ProjectModule]) -> str:
    best, best_len = "", -1
    for m in modules:
        for rule in (m.path_rules or []):
            r = rule.strip().lstrip("./").rstrip("*")
            if r and path.startswith(r) and len(r) > best_len:
                best, best_len = m.name, len(r)
    return best or "其他"


def _tree_text(files: list[str], limit: int = 400) -> str:
    return "\n".join(sorted(files)[:limit])


def _symbols_text(content: str, lang: str) -> str:
    syms = diff_parser.extract_symbols(content, lang)
    return ", ".join(f"{s.name}({s.kind})" for s in syms[:40])


def _get_or_create_file(db: Session, repo: Repository, path: str,
                        modules: list[ProjectModule], cfg: SystemConfig,
                        repo_path: str, ref: str) -> SourceFile:
    sf = db.scalar(select(SourceFile).where(SourceFile.repo_id == repo.id,
                                            SourceFile.path == path))
    if sf:
        return sf
    content = git_service.file_content(repo_path, path, ref)
    lang = diff_parser.lang_of(path)
    module_name = _match_module(path, modules)
    baseline, mode = llm_service.file_baseline(cfg, path, content,
                                               _symbols_text(content, lang), module_name)
    _, files_dir, _ = _repo_dirs(repo.id)
    doc_path = _write_md(files_dir, path, baseline.doc_md)
    sf = SourceFile(repo_id=repo.id, path=path, module_name=module_name,
                    language=lang or "其他", one_liner=baseline.one_liner,
                    current_doc=baseline.doc_md, baseline_doc_path=doc_path,
                    evolution_line="")
    db.add(sf)
    db.flush()
    return sf


def _commit_url(cfg: SystemConfig, sha: str) -> str:
    base = (cfg.commit_web_base_url or "").strip().rstrip("/")
    return f"{base}/commit/{sha}" if base else ""


def _module_capability(blocks: list[dict], new_files: list[str],
                       summary: str) -> str:
    """从代码块与新文件归纳模块本次「能力变化」，确定性、不脑补。"""
    added = [b.get("name", "") for b in blocks
             if b.get("change_type") == "added" and b.get("precision") == "function"
             and b.get("name")]
    removed = [b.get("name", "") for b in blocks
               if b.get("change_type") == "removed" and b.get("precision") == "function"
               and b.get("name")]
    modified = [b.get("name", "") for b in blocks
                if b.get("change_type") not in ("added", "removed")
                and b.get("precision") == "function" and b.get("name")]
    parts: list[str] = []
    if new_files:
        shown = "、".join(p.replace("\\", "/").split("/")[-1] for p in new_files[:3])
        parts.append(f"引入新文件 {shown}")
    if added:
        parts.append("新增 " + "、".join(added[:5]))
    if removed:
        parts.append("移除 " + "、".join(removed[:5]))
    if modified:
        parts.append("调整 " + "、".join(modified[:5]))
    return "；".join(parts)[:220] or (summary or "").strip()[:180]


def _discover_module_candidates(db: Session, repo: Repository,
                                new_paths: list[str], commit: git_service.CommitInfo,
                                modules: list[ProjectModule]) -> list[str]:
    """从「不属于任何现有模块」的新增源码文件里发现新功能模块候选。"""
    created: list[str] = []
    groups: dict[str, list[str]] = {}
    for path in new_paths:
        if not signal_filter.is_source_path(path):
            continue
        if _match_module(path, modules) != "其他":
            continue
        posix = path.replace("\\", "/").strip("/")
        parts = posix.split("/")
        prefix = "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else "")
        rule = (prefix + "/") if prefix else posix
        groups.setdefault(rule, []).append(posix)

    pending = db.scalars(select(ModuleCandidate).where(
        ModuleCandidate.repo_id == repo.id,
        ModuleCandidate.status == "pending")).all()
    for rule, paths in groups.items():
        existing = next((c for c in pending if rule in (c.path_rules or [])), None)
        label = rule.rstrip("/").split("/")[-1] or paths[0].split("/")[-1]
        if existing:
            samples = list(existing.sample_files or [])
            for p in paths:
                if p not in samples:
                    samples.append(p)
            existing.sample_files = samples[:12]
            existing.evidence_commit = commit.sha
            existing.reason = (f"提交 {commit.sha[:7]} 持续新增未被现有模块覆盖的源码文件，"
                               f"疑似新功能模块：{', '.join(paths[:3])}")
            continue
        # 与已有模块重名时，用完整路径前缀避免混淆
        name = label
        if any(m.name == name for m in modules):
            name = rule.rstrip("/").replace("/", " / ")
        cand = ModuleCandidate(
            repo_id=repo.id, name=name, path_rules=[rule],
            reason=(f"提交 {commit.sha[:7]} 新增了未被现有模块覆盖的源码文件，"
                    f"疑似新功能模块：{', '.join(paths[:3])}"),
            evidence_commit=commit.sha, sample_files=paths[:12], status="pending")
        db.add(cand)
        created.append(name)
    if created:
        db.flush()
    return created


def _module_files_text(db: Session, repo_id: int, module_name: str) -> str:
    rows = db.scalars(select(SourceFile).where(SourceFile.repo_id == repo_id,
                                              SourceFile.module_name == module_name)
                      .order_by(SourceFile.path)).all()
    return "\n".join(f"{f.path} — {f.one_liner or '职责待补充'}" for f in rows[:60])


def _refresh_module_archive(db: Session, pm: ProjectModule, cfg: SystemConfig) -> None:
    """修订模块当前态档案（含能力变化与职责演进主线）并落盘。"""
    events = db.scalars(select(ModuleChangeEvent).where(
        ModuleChangeEvent.module_id == pm.id)
        .order_by(ModuleChangeEvent.committed_at.asc().nullslast(),
                  ModuleChangeEvent.id.asc())).all()
    if not pm.current_doc:
        one, doc, _ = llm_service.module_baseline(
            cfg, pm.name, pm.responsibility, _module_files_text(db, pm.repo_id, pm.name))
        pm.one_liner = one
        pm.current_doc = doc
    if events:
        latest = events[-1]
        pm.current_doc = llm_service.append_module_history(
            pm.current_doc, latest.capability_delta, latest.summary, latest.commit_sha[:7])
        payload = [{"sha_short": e.commit_sha[:7], "message": e.commit_message,
                    "capability": e.capability_delta, "summary": e.summary,
                    "motivation": e.motivation} for e in events[-20:]]
        pm.evolution_line, _ = llm_service.module_evolution(
            cfg, pm.name, pm.evolution_line or "", payload)
        pm.last_commit_sha = latest.commit_sha
    _, _, modules_dir = _repo_dirs(pm.repo_id)
    pm.doc_path = _write_md(modules_dir, pm.name, pm.current_doc)


def _module_status_by_age(db: Session, pm: ProjectModule) -> str:
    latest = db.scalar(select(func.max(ModuleChangeEvent.committed_at))
                       .where(ModuleChangeEvent.module_id == pm.id))
    if not latest:
        return "active"
    return "dormant" if (datetime.now() - latest).days >= 180 else "active"


def _analyze_one_commit(db: Session, repo: Repository, cfg: SystemConfig,
                        repo_path: str, commit: git_service.CommitInfo,
                        branch: str, modules: list[ProjectModule],
                        cb: ProgressCB | None = None,
                        discover_candidates: bool = True,
                        issues: list[Issue] | None = None,
                        use_llm_link: bool = False) -> dict:
    """分析单条提交：过滤 → 代码块解析 → 文件/模块双视角落库 → 档案演进 → 需求关联。"""
    module_hits: dict[str, dict] = {}
    new_paths: list[str] = []
    # 幂等：同分支同提交已分析则跳过
    if db.scalar(select(CommitAnalysis).where(CommitAnalysis.repo_id == repo.id,
                                              CommitAnalysis.commit_sha == commit.sha,
                                              CommitAnalysis.branch == branch)):
        return {"skipped": True}

    diff_text = git_service.commit_diff(repo_path, commit.sha, cfg.max_diff_chars)
    fds = diff_parser.parse_diff(diff_text)
    verdict = signal_filter.classify_commit(commit.message, fds)

    if not verdict.is_high_signal:
        ca = CommitAnalysis(
            repo_id=repo.id, commit_sha=commit.sha, branch=branch, author=commit.author,
            committed_at=commit.committed_at, message=commit.message,
            summary="低信号提交，未纳入知识时间线", motivation=llm_service.NO_MOTIVATION,
            evidence_source="未知", affected_files=[fd.path for fd in fds],
            diff_stats={"added": sum(f.added for f in fds), "deleted": sum(f.deleted for f in fds),
                        "files": len(fds)}, risk_level="低", is_high_signal=False,
            filter_reason=verdict.reason, analysis_mode="本地规则")
        db.add(ca)
        db.flush()
        linked = issue_linker.link_commit(db, repo.id, ca, issues, cfg, use_llm=use_llm_link)
        return {"filtered": True, "reason": verdict.reason, "issue_links": len(linked)}

    # 为每个文件补充代码块级结构（需要新旧文件内容做函数边界识别）
    parent = f"{commit.sha}^"
    ref = commit.sha
    for fd in verdict.kept_files:
        old_content = git_service.file_content(repo_path, fd.old_path or fd.path, parent)
        new_content = git_service.file_content(repo_path, fd.path, ref) if fd.status != "D" else ""
        fd.blocks = diff_parser.build_blocks(fd, old_content, new_content)
        fd.precision = "hunk" if any(b["precision"] == "hunk" for b in fd.blocks) else "function"

    result, mode = llm_service.analyze_commit(cfg, commit.message, verdict.kept_files,
                                              cfg.max_diff_chars)
    file_results = {fr.path: fr for fr in result.files}
    diff_stats = {"added": sum(f.added for f in verdict.kept_files),
                  "deleted": sum(f.deleted for f in verdict.kept_files),
                  "files": len(verdict.kept_files)}
    ca = CommitAnalysis(
        repo_id=repo.id, commit_sha=commit.sha, branch=branch, author=commit.author,
        committed_at=commit.committed_at, message=commit.message, summary=result.summary,
        motivation=result.motivation, evidence_source=result.evidence_source,
        affected_files=[fd.path for fd in verdict.kept_files], diff_stats=diff_stats,
        risk_level=result.risk_level, is_high_signal=True, filter_reason=verdict.reason,
        analysis_mode=mode)
    db.add(ca)
    db.flush()

    touched: list[tuple[SourceFile, dict]] = []
    for fd in verdict.kept_files:
        fr = file_results.get(fd.path)
        sf = _get_or_create_file(db, repo, fd.path, modules, cfg, repo_path, ref)
        blocks_payload = []
        llm_blocks = {b.name: b for b in (fr.blocks if fr else [])}
        for b in fd.blocks[:20]:
            desc = llm_blocks.get(b["name"])
            blocks_payload.append({
                "name": b["name"], "kind": b["kind"], "precision": b["precision"],
                "change_type": b["change_type"], "old_range": b["old_range"],
                "new_range": b["new_range"], "added_lines": b["added_lines"],
                "removed_lines": b["removed_lines"],
                "description": (desc.description if desc else
                                f"{diff_parser.CHANGE_TYPE_CN.get(b['change_type'], '修改')} "
                                f"+{b['added_lines']}/-{b['removed_lines']} 行"),
            })
        doc_update = (fr.doc_update if fr and fr.doc_update else
                      f"记录 {len(blocks_payload)} 处代码块变更")
        exists = db.scalar(select(FileChangeEvent).where(
            FileChangeEvent.source_file_id == sf.id,
            FileChangeEvent.commit_sha == commit.sha))
        if not exists:
            ev = FileChangeEvent(
                source_file_id=sf.id, repo_id=repo.id, commit_sha=commit.sha, branch=branch,
                author=commit.author, committed_at=commit.committed_at,
                commit_message=commit.message, summary=result.summary,
                blocks=blocks_payload, doc_update=doc_update,
                motivation=result.motivation, evidence_source=result.evidence_source,
                risk_level=result.risk_level,
                diff_stats={"added": fd.added, "deleted": fd.deleted, "precision": fd.precision},
                analysis_mode=mode)
            db.add(ev)
            sf.last_commit_sha = commit.sha
            sf.risk_level = result.risk_level
            sf.change_count = (sf.change_count or 0) + 1
            if fr and fr.one_liner:
                sf.one_liner = fr.one_liner
            touched.append((sf, {"summary": result.summary, "doc_update": doc_update,
                                 "one_liner": sf.one_liner, "blocks": blocks_payload}))
        mname = sf.module_name or "其他"
        bucket = module_hits.setdefault(mname, {"files": [], "blocks": [], "new_files": []})
        bucket["files"].append(fd.path)
        bucket["blocks"].extend(blocks_payload)
        if fd.status == "A":
            bucket["new_files"].append(fd.path)
            new_paths.append(fd.path)
    db.flush()

    # 当前态文档增量修订 + 跨提交演进主线归纳
    for sf, info in touched:
        new_doc, _ = llm_service.update_current_doc(
            cfg, sf.path, sf.current_doc or "", info["summary"],
            info["doc_update"], info["one_liner"], info["blocks"])
        sf.current_doc = new_doc
        _, files_dir, _ = _repo_dirs(repo.id)
        sf.baseline_doc_path = _write_md(files_dir, sf.path, new_doc)
        events = db.scalars(select(FileChangeEvent).where(
            FileChangeEvent.source_file_id == sf.id)
            .order_by(FileChangeEvent.committed_at.asc(), FileChangeEvent.id.asc())).all()
        ev_payload = []
        for e in events[-20:]:
            added = [b.get("name", "") for b in (e.blocks or [])
                     if b.get("change_type") == "added" and b.get("precision") == "function"]
            capability = "新增 " + "、".join(added[:4]) if added else ""
            ev_payload.append({"sha_short": e.commit_sha[:7], "summary": e.summary,
                               "message": e.commit_message, "capability": capability,
                               "motivation": e.motivation})
        line, _ = llm_service.evolution_line(cfg, sf.path, sf.evolution_line or "", ev_payload)
        sf.evolution_line = line

    # 模块视角：一次提交对每个受影响模块生成一条时间线节点，并修订模块档案
    for mname, bucket in module_hits.items():
        pm = next((m for m in modules if m.name == mname), None)
        if pm is None:
            continue
        capability = _module_capability(bucket["blocks"], bucket["new_files"], result.summary)
        exists = db.scalar(select(ModuleChangeEvent).where(
            ModuleChangeEvent.repo_id == repo.id, ModuleChangeEvent.module_id == pm.id,
            ModuleChangeEvent.commit_sha == commit.sha, ModuleChangeEvent.branch == branch))
        if not exists:
            db.add(ModuleChangeEvent(
                repo_id=repo.id, module_id=pm.id, module_name=pm.name,
                commit_sha=commit.sha, branch=branch, author=commit.author,
                committed_at=commit.committed_at, commit_message=commit.message,
                summary=result.summary, capability_delta=capability,
                affected_files=bucket["files"], motivation=result.motivation,
                evidence_source=result.evidence_source, risk_level=result.risk_level,
                analysis_mode=mode))
            pm.change_count = (pm.change_count or 0) + 1
            pm.status = "active"
        _refresh_module_archive(db, pm, cfg)
    db.flush()

    # 新功能发现：新增且不属于任何现有模块的文件 → 候选模块（不自动建模块）
    created = (_discover_module_candidates(db, repo, new_paths, commit, modules)
               if discover_candidates else [])

    # 需求/缺陷追溯：自动关联 + 四项信号证据评级（动机从「原因未知」升级为需求单来源）
    linked = issue_linker.link_commit(db, repo.id, ca, issues, cfg, use_llm=use_llm_link)
    db.flush()
    return {"analyzed": True, "files": len(touched), "modules": len(module_hits),
            "module_candidates": created, "issue_links": len(linked),
            "mode": mode, "risk": result.risk_level}


# ---------------------------------------------------------------------------
# 全量初始化
# ---------------------------------------------------------------------------

def initialize(db: Session, repo_id: int, cb: ProgressCB | None = None,
               history_limit: int = 60, max_files: int = 300, **_) -> dict:
    cb = cb or (lambda p, m: None)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise RuntimeError("仓库不存在")
    cb(2, "准备仓库路径")
    if repo.source_type == "remote":
        repo.local_path = git_service.clone_remote(repo.source, repo.id)
    else:
        repo.local_path = git_service.normalize_local_path(repo.source)
        if not git_service.is_git_repo(repo.local_path):
            raise RuntimeError(f"不是有效的 Git 仓库：{repo.local_path}")
    repo.status = "initializing"
    repo.status_message = "正在初始化扫描"
    db.commit()

    cfg = llm_service.get_config(db)
    repo_path = repo.local_path
    branches = repo.branches or [repo.default_branch]
    primary = branches[0]
    ref = git_service.resolve_ref(repo_path, primary) or git_service.head_sha(repo_path) or "HEAD"

    cb(8, "扫描目录结构")
    all_files = git_service.tracked_files(repo_path, ref)
    source_files = [p for p in all_files if signal_filter.is_source_path(p)]
    # 优先核心代码文件，控制建档数量
    source_files = sorted(source_files, key=lambda p: (0 if diff_parser.lang_of(p) else 1, p))[:max_files]
    cb(14, f"共 {len(all_files)} 个跟踪文件，{len(source_files)} 个待建档")

    cb(20, "统计历史文件共变关系")
    cochange = git_service.co_change_stats(repo_path, ref, limit=150)
    cochange_text = "\n".join(
        [f"- {p['a']} 与 {p['b']} 共同变更 {p['count']} 次" for p in cochange[0]["pairs"][:25]] +
        [f"- 热点文件 {h['path']} 出现 {h['count']} 次" for h in cochange[0]["hot_files"][:20]])

    cb(26, "归纳项目功能模块清单")
    cluster, mode = llm_service.cluster_modules(cfg, _tree_text(all_files), cochange_text)
    db.query(ProjectModule).filter(ProjectModule.repo_id == repo.id).delete()
    db.flush()
    _, _, modules_dir = _repo_dirs(repo.id)
    modules: list[ProjectModule] = []
    for item in cluster.modules:
        pm = ProjectModule(repo_id=repo.id, name=item.name, path_rules=item.path_rules,
                           responsibility=item.responsibility, status="active")
        db.add(pm)
        modules.append(pm)
    db.flush()
    for pm in modules:
        pm.file_count = sum(1 for p in source_files if _match_module(p, modules) == pm.name)
    cb(34, f"模块聚类完成（{len(modules)} 个模块，{mode}）")

    cb(38, "生成单文件基线档案")
    for i, p in enumerate(source_files):
        _get_or_create_file(db, repo, p, modules, cfg, repo_path, ref)
        if i % 20 == 0:
            cb(38 + int(20 * i / max(len(source_files), 1)), f"已建档 {i + 1}/{len(source_files)} 个文件")
    db.flush()
    cb(56, "生成功能模块档案")
    for pm in modules:
        one, doc, _ = llm_service.module_baseline(
            cfg, pm.name, pm.responsibility, _module_files_text(db, repo.id, pm.name))
        doc = doc.rstrip() + "\n\n## 路径规则\n\n" + (
            "\n".join(f"- `{r}`" for r in (pm.path_rules or [])) or "- （无）") + "\n"
        pm.one_liner, pm.current_doc = one, doc
        pm.doc_path = _write_md(modules_dir, pm.name, doc)
    db.flush()
    cb(58, f"文件基线建档完成（{len(source_files)} 个，模块档案 {len(modules)} 份）")

    cb(60, "回溯历史高信号提交，构建变更时间线")
    issues = list(db.scalars(select(Issue).where(Issue.repo_id == repo.id)).all())
    commits = git_service.log_recent(repo_path, ref, limit=max(history_limit, 1))
    commits = list(reversed(commits))  # 按时间正序
    analyzed = filtered = linked = 0
    total = max(len(commits), 1)
    for i, c in enumerate(commits):
        r = _analyze_one_commit(db, repo, cfg, repo_path, c, primary, modules,
                                discover_candidates=False, issues=issues)
        if r.get("filtered"):
            filtered += 1
        elif r.get("analyzed"):
            analyzed += 1
        linked += r.get("issue_links", 0)
        if i % 5 == 0:
            cb(60 + int(32 * (i + 1) / total), f"历史提交 {i + 1}/{total}（分析 {analyzed} / 过滤 {filtered}）")
    # 回填此前已存在、尚未建立关联的提交（例如先分析仓库、后补录需求）
    linked += issue_linker.relink_repo(db, repo.id, use_llm=False)["new_links"]
    db.flush()
    cb(92, "建立分支水位线")
    for br in branches:
        sha = git_service.resolve_ref(repo_path, br)
        if not sha:
            continue
        state = db.scalar(select(BranchState).where(BranchState.repo_id == repo.id,
                                                    BranchState.branch == br))
        if state is None:
            state = BranchState(repo_id=repo.id, branch=br, last_commit_sha=sha)
            db.add(state)
        else:
            state.last_commit_sha = sha
    repo.status = "ready"
    repo.status_message = (f"初始化完成：{len(source_files)} 个文件档案，{analyzed} 条历史分析，"
                           f"{linked} 条需求关联")
    repo.last_analyzed_at = datetime.now()
    db.commit()
    cb(100, repo.status_message)
    return {"files": len(source_files), "modules": len(modules),
            "commits_analyzed": analyzed, "commits_filtered": filtered,
            "issue_links": linked, "branches": branches, "cluster_mode": mode}


# ---------------------------------------------------------------------------
# 增量同步
# ---------------------------------------------------------------------------

def incremental_sync(db: Session, repo_id: int, cb: ProgressCB | None = None,
                     branch: str = "", force_rebuild: bool = False, **_) -> dict:
    cb = cb or (lambda p, m: None)
    repo = db.get(Repository, repo_id)
    if not repo:
        raise RuntimeError("仓库不存在")
    if not repo.local_path:
        raise RuntimeError("仓库尚未初始化，请先执行初始化扫描")
    repo.status = "syncing"
    repo.status_message = "正在增量同步"
    db.commit()

    cfg = llm_service.get_config(db)
    repo_path = repo.local_path
    cb(5, "拉取远端更新")
    if repo.source_type == "remote":
        git_service.fetch_all(repo_path)
    branches = [branch] if branch else (repo.branches or [repo.default_branch])
    modules = db.scalars(select(ProjectModule).where(ProjectModule.repo_id == repo.id)).all()
    issues = list(db.scalars(select(Issue).where(Issue.repo_id == repo.id)).all())
    summary: dict = {"branches": {}, "total_new": 0, "total_analyzed": 0,
                     "total_filtered": 0, "new_module_candidates": 0,
                     "total_issue_links": 0}

    for bi, br in enumerate(branches):
        state = db.scalar(select(BranchState).where(BranchState.repo_id == repo.id,
                                                    BranchState.branch == br))
        if state is None:
            state = BranchState(repo_id=repo.id, branch=br, last_commit_sha="")
            db.add(state)
            db.flush()
        head = git_service.resolve_ref(repo_path, br)
        if not head:
            summary["branches"][br] = {"error": "分支不存在"}
            continue
        if state.last_commit_sha == head and not force_rebuild and state.last_commit_sha:
            summary["branches"][br] = {"new": 0, "note": "已是最新"}
            continue
        if state.last_commit_sha:
            commits = git_service.log_range(repo_path, state.last_commit_sha, br)
        else:
            # 新分支无水位线时只回溯最近 60 条，避免全量历史拖慢首次同步
            commits = list(reversed(git_service.log_recent(repo_path, br, limit=60)))
        cb(15 + int(60 * bi / max(len(branches), 1)), f"分支 {br} 发现 {len(commits)} 条新提交")
        analyzed = filtered = 0
        for i, c in enumerate(commits):
            r = _analyze_one_commit(db, repo, cfg, repo_path, c, br, modules,
                                    issues=issues, use_llm_link=True)
            if r.get("filtered"):
                filtered += 1
            elif r.get("analyzed"):
                analyzed += 1
            summary["new_module_candidates"] += len(r.get("module_candidates") or [])
            summary["total_issue_links"] += r.get("issue_links", 0)
            if commits and i % 3 == 0:
                cb(20 + int(60 * (bi + (i + 1) / len(commits)) / len(branches)),
                   f"{br}: {i + 1}/{len(commits)} 条提交")
        state.last_commit_sha = head
        summary["branches"][br] = {"new": len(commits), "analyzed": analyzed, "filtered": filtered}
        summary["total_new"] += len(commits)
        summary["total_analyzed"] += analyzed
        summary["total_filtered"] += filtered
    db.flush()

    # 同步模块覆盖文件数、活跃状态与档案
    for pm in modules:
        pm.file_count = db.scalar(select(func.count()).select_from(SourceFile).where(
            SourceFile.repo_id == repo.id, SourceFile.module_name == pm.name)) or 0
        pm.status = _module_status_by_age(db, pm)
        _refresh_module_archive(db, pm, cfg)
    db.flush()
    pending = db.scalar(select(func.count()).select_from(ModuleCandidate).where(
        ModuleCandidate.repo_id == repo.id, ModuleCandidate.status == "pending")) or 0
    summary["pending_candidates"] = pending
    # 补录需求后，回填历史提交里尚未建立的关联（AI 复核只对新提交启用，控制成本）
    summary["total_issue_links"] += issue_linker.relink_repo(
        db, repo.id, use_llm=False)["new_links"]
    repo.status = "ready"
    repo.status_message = (f"同步完成：新增 {summary['total_new']} 条提交，"
                           f"分析 {summary['total_analyzed']} 条，过滤 {summary['total_filtered']} 条"
                           f"，建立 {summary['total_issue_links']} 条需求关联"
                           + (f"；发现 {summary['new_module_candidates']} 个新功能候选"
                              if summary["new_module_candidates"] else ""))
    repo.last_analyzed_at = datetime.now()
    db.commit()
    cb(100, repo.status_message)
    return summary


# ---------------------------------------------------------------------------
# 新功能模块候选的人工确认
# ---------------------------------------------------------------------------

def confirm_candidate(db: Session, candidate_id: int, custom_name: str = "") -> dict:
    """确认候选 → 建立功能模块 → 重新归属文件 → 生成模块档案。"""
    cand = db.get(ModuleCandidate, candidate_id)
    if not cand:
        raise RuntimeError("候选不存在")
    if cand.status != "pending":
        raise RuntimeError("该候选已处理")
    name = (custom_name or "").strip() or cand.name
    if db.scalar(select(ProjectModule).where(ProjectModule.repo_id == cand.repo_id,
                                             ProjectModule.name == name)):
        raise RuntimeError(f"模块「{name}」已存在，请换一个名称")
    pm = ProjectModule(
        repo_id=cand.repo_id, name=name, path_rules=list(cand.path_rules or []),
        responsibility=(f"由提交 {(cand.evidence_commit or '')[:7]} 引入的新功能模块，"
                        f"包含 {len(cand.sample_files or [])} 个源码文件"),
        status="active")
    db.add(pm)
    db.flush()

    modules = db.scalars(select(ProjectModule).where(
        ProjectModule.repo_id == cand.repo_id)).all()
    for sf in db.scalars(select(SourceFile).where(
            SourceFile.repo_id == cand.repo_id)).all():
        matched = _match_module(sf.path, modules)
        if matched != sf.module_name:
            sf.module_name = matched
    db.flush()
    pm.file_count = db.scalar(select(func.count()).select_from(SourceFile).where(
        SourceFile.repo_id == cand.repo_id, SourceFile.module_name == pm.name)) or 0

    cfg = llm_service.get_config(db)
    one, doc, _ = llm_service.module_baseline(
        cfg, pm.name, pm.responsibility, _module_files_text(db, cand.repo_id, pm.name))
    doc = doc.rstrip() + "\n\n## 路径规则\n\n" + (
        "\n".join(f"- `{r}`" for r in (pm.path_rules or [])) or "- （无）") + "\n"
    pm.one_liner, pm.current_doc = one, doc
    _, _, modules_dir = _repo_dirs(cand.repo_id)
    pm.doc_path = _write_md(modules_dir, pm.name, doc)

    # 把触发发现的提交补成新模块的第一条时间线节点，保证一建立即可追溯
    ca = db.scalar(select(CommitAnalysis).where(
        CommitAnalysis.repo_id == cand.repo_id,
        CommitAnalysis.commit_sha == cand.evidence_commit)) if cand.evidence_commit else None
    if ca and not db.scalar(select(ModuleChangeEvent).where(
            ModuleChangeEvent.module_id == pm.id,
            ModuleChangeEvent.commit_sha == ca.commit_sha)):
        affected = [p for p in (ca.affected_files or [])
                    if _match_module(p, modules) == pm.name]
        db.add(ModuleChangeEvent(
            repo_id=cand.repo_id, module_id=pm.id, module_name=pm.name,
            commit_sha=ca.commit_sha, branch=ca.branch, author=ca.author,
            committed_at=ca.committed_at, commit_message=ca.message,
            summary=ca.summary,
            capability_delta=f"新功能引入：{', '.join(affected[:3]) or cand.name}",
            affected_files=affected, motivation=ca.motivation,
            evidence_source=ca.evidence_source, risk_level=ca.risk_level,
            analysis_mode=ca.analysis_mode))
        pm.change_count = 1
        pm.last_commit_sha = ca.commit_sha
        db.flush()
        _refresh_module_archive(db, pm, cfg)

    cand.status = "confirmed"
    cand.decided_at = datetime.now()
    db.commit()
    return {"id": pm.id, "name": pm.name, "file_count": pm.file_count,
            "path_rules": pm.path_rules}


def ignore_candidate(db: Session, candidate_id: int) -> dict:
    cand = db.get(ModuleCandidate, candidate_id)
    if not cand:
        raise RuntimeError("候选不存在")
    cand.status = "ignored"
    cand.decided_at = datetime.now()
    db.commit()
    return {"id": candidate_id, "status": "ignored"}
