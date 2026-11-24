"""分析业务服务：初始化 / 增量同步 / 模块候选处理。

把 analyzers/analyzer.py 的纯分析逻辑接入分层架构：
后台线程用 SessionLocal 注入会话，JobManager 统一在 services 层暴露。
"""
from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from ..analyzers import analyzer
from ..core.errors import NotFoundError
from ..db.session import SessionLocal
from ..models.project import Repository

jobs = analyzer.jobs  # JobManager 单例，供 API 轮询


def _get_repo_or_404(db: Session, repo_id: int) -> Repository:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFoundError("仓库")
    return repo


def initialize(db: Session, repo_id: int, history_limit: int = 60, max_files: int = 300) -> str:
    _get_repo_or_404(db, repo_id)
    jid = jobs.create("initialize", repo_id)
    jobs.start(jid, "initialize", repo_id,
               history_limit=history_limit, max_files=max_files)
    return jid


def incremental_sync(db: Session, repo_id: int, branch: str = "", force_rebuild: bool = False) -> str:
    _get_repo_or_404(db, repo_id)
    jid = jobs.create("sync", repo_id)
    jobs.start(jid, "sync", repo_id, branch=branch, force_rebuild=force_rebuild)
    return jid


def get_job(job_id: str) -> dict | None:
    return jobs.get(job_id)


def confirm_candidate(db: Session, candidate_id: int, custom_name: str = "") -> dict:
    return analyzer.confirm_candidate(db, candidate_id, custom_name)


def ignore_candidate(db: Session, candidate_id: int) -> dict:
    return analyzer.ignore_candidate(db, candidate_id)
