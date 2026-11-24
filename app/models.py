"""数据模型：系统配置 / 仓库 / 分支水位线 / 模块 / 文件 / 变更事件 / 提交分析 / 需求缺陷追溯。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.now()


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_url: Mapped[str] = mapped_column(String(500), default="https://api.openai.com/v1")
    api_key: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(200), default="gpt-4o-mini")
    max_diff_chars: Mapped[int] = mapped_column(Integer, default=12000)
    commit_web_base_url: Mapped[str] = mapped_column(String(500), default="")
    llm_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(Text)                  # 本地路径或远程地址
    source_type: Mapped[str] = mapped_column(String(20), default="local")  # local | remote
    local_path: Mapped[str] = mapped_column(Text, default="")
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    branches: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|initializing|ready|syncing|error
    status_message: Mapped[str] = mapped_column(Text, default="")
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BranchState(Base):
    """每个受监控分支独立记录分析水位线。"""
    __tablename__ = "branch_states"
    __table_args__ = (UniqueConstraint("repo_id", "branch", name="uq_repo_branch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    branch: Mapped[str] = mapped_column(String(200))
    last_commit_sha: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ProjectModule(Base):
    __tablename__ = "project_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(200))
    path_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    responsibility: Mapped[str] = mapped_column(Text, default="")
    doc_path: Mapped[str] = mapped_column(Text, default="")
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    one_liner: Mapped[str] = mapped_column(Text, default="")
    current_doc: Mapped[str] = mapped_column(Text, default="")
    evolution_line: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | dormant | new
    last_commit_sha: Mapped[str] = mapped_column(String(64), default="")
    change_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ModuleChangeEvent(Base):
    """模块时间线节点：一次提交对该功能模块的整体影响。"""
    __tablename__ = "module_change_events"
    __table_args__ = (UniqueConstraint("repo_id", "module_id", "commit_sha", "branch",
                                       name="uq_module_commit_branch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    module_id: Mapped[int] = mapped_column(Integer, index=True)
    module_name: Mapped[str] = mapped_column(String(200), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), index=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    author: Mapped[str] = mapped_column(String(200), default="")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    capability_delta: Mapped[str] = mapped_column(Text, default="")
    affected_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    motivation: Mapped[str] = mapped_column(Text, default="原因未知（证据不足）")
    evidence_source: Mapped[str] = mapped_column(String(40), default="未知")
    risk_level: Mapped[str] = mapped_column(String(10), default="低")
    analysis_mode: Mapped[str] = mapped_column(String(20), default="本地规则")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ModuleCandidate(Base):
    """新功能模块候选：由新增文件/新目录自动发现，等待人工确认。"""
    __tablename__ = "module_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(200))
    path_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_commit: Mapped[str] = mapped_column(String(64), default="")
    sample_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | confirmed | ignored
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SourceFile(Base):
    """单文件档案：当前态说明 + 跨提交演进主线。"""
    __tablename__ = "source_files"
    __table_args__ = (UniqueConstraint("repo_id", "path", name="uq_repo_file"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    path: Mapped[str] = mapped_column(Text)
    module_name: Mapped[str] = mapped_column(String(200), default="")
    language: Mapped[str] = mapped_column(String(40), default="")
    one_liner: Mapped[str] = mapped_column(Text, default="")
    current_doc: Mapped[str] = mapped_column(Text, default="")
    evolution_line: Mapped[str] = mapped_column(Text, default="")
    baseline_doc_path: Mapped[str] = mapped_column(Text, default="")
    last_commit_sha: Mapped[str] = mapped_column(String(64), default="")
    risk_level: Mapped[str] = mapped_column(String(10), default="低")
    change_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class FileChangeEvent(Base):
    """文件时间线上的一个节点：一次提交对该文件的改动。"""
    __tablename__ = "file_change_events"
    __table_args__ = (UniqueConstraint("source_file_id", "commit_sha", name="uq_file_commit"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_id: Mapped[int] = mapped_column(Integer, index=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    commit_sha: Mapped[str] = mapped_column(String(64), index=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    author: Mapped[str] = mapped_column(String(200), default="")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    doc_update: Mapped[str] = mapped_column(Text, default="")
    motivation: Mapped[str] = mapped_column(Text, default="原因未知（证据不足）")
    evidence_source: Mapped[str] = mapped_column(String(40), default="未知")
    risk_level: Mapped[str] = mapped_column(String(10), default="低")
    diff_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    analysis_mode: Mapped[str] = mapped_column(String(20), default="本地规则")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CommitAnalysis(Base):
    """全局提交检索记录。"""
    __tablename__ = "commit_analyses"
    __table_args__ = (UniqueConstraint("repo_id", "commit_sha", "branch", name="uq_commit_branch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    commit_sha: Mapped[str] = mapped_column(String(64), index=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    author: Mapped[str] = mapped_column(String(200), default="")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    motivation: Mapped[str] = mapped_column(Text, default="原因未知（证据不足）")
    evidence_source: Mapped[str] = mapped_column(String(40), default="未知")
    affected_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    diff_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(10), default="低")
    is_high_signal: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_reason: Mapped[str] = mapped_column(Text, default="")
    analysis_mode: Mapped[str] = mapped_column(String(20), default="本地规则")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Issue(Base):
    """需求 / 缺陷实体：只登记「为什么要改」，不做任务分配、工时与看板。"""
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repo_id", "external_id", name="uq_repo_issue_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    external_id: Mapped[str] = mapped_column(String(100))   # "#123" / "BUG-1" / "PROJ-42"
    issue_type: Mapped[str] = mapped_column(String(20), default="bug")  # bug | story
    title: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | resolved | closed
    source: Mapped[str] = mapped_column(String(30), default="manual")  # manual | zentao | jira | csv
    external_url: Mapped[str] = mapped_column(Text, default="")
    reporter: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    related_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class IssueCommitLink(Base):
    """需求/缺陷 ↔ 提交 的关联与修复证据评级。

    关联分三级：explicit（提交明确引用）/ semantic（关键词推测）/ inferred（上下文推断）/ manual（人工挂载）。
    结论只做证据充分性评级，绝不输出「已修复」这类运行时判断。
    """
    __tablename__ = "issue_commit_links"
    __table_args__ = (UniqueConstraint("issue_id", "commit_sha", name="uq_issue_commit"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(Integer, index=True)
    issue_id: Mapped[int] = mapped_column(Integer, index=True)
    commit_sha: Mapped[str] = mapped_column(String(64), index=True)
    branch: Mapped[str] = mapped_column(String(200), default="")
    link_type: Mapped[str] = mapped_column(String(20), default="semantic")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    assessment: Mapped[str] = mapped_column(String(20), default="weak")  # strong | weak | review
    assessment_label: Mapped[str] = mapped_column(String(100), default="")
    assessment_note: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(20), default="pending")  # confirmed | pending | rejected
    llm_note: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
