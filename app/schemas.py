"""Pydantic v2：API 入参校验 + LLM 结构化输出校验。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------- API 入参 ----------------

class RepoCreate(BaseModel):
    source: str = Field(..., min_length=1, description="本地 Git 路径或远程地址")
    source_type: str = Field(default="local")
    name: str = ""
    default_branch: str = "main"
    branches: list[str] = Field(default_factory=list)

    @field_validator("source_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ("local", "remote"):
            raise ValueError("source_type 只能是 local 或 remote")
        return v


class ConfigUpdate(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    max_diff_chars: int = 12000
    commit_web_base_url: str = ""
    llm_enabled: bool = True

    @field_validator("max_diff_chars")
    @classmethod
    def _check_chars(cls, v: int) -> int:
        return max(1000, min(v, 100000))


class SyncRequest(BaseModel):
    branch: str = ""          # 空 = 全部受监控分支
    force_rebuild: bool = False


class InitRequest(BaseModel):
    history_limit: int = 60   # 冷启动回溯的历史提交数
    max_files: int = 300      # 建档文件上限


class IssueCreate(BaseModel):
    external_id: str
    issue_type: str = "bug"
    title: str = ""
    description: str = ""
    status: str = "open"
    source: str = "manual"
    external_url: str = ""
    reporter: str = ""
    keywords: list[str] = Field(default_factory=list)
    related_paths: list[str] = Field(default_factory=list)
    occurred_at: str = ""


class IssueImport(BaseModel):
    csv_text: str
    source: str = "csv"


# ---------------- LLM 结构化输出 ----------------

class ModuleItem(BaseModel):
    name: str
    path_rules: list[str] = Field(default_factory=list)
    responsibility: str = ""


class ModuleClusterResult(BaseModel):
    modules: list[ModuleItem] = Field(default_factory=list)


class FileBaselineResult(BaseModel):
    one_liner: str = ""
    doc_md: str = ""


class BlockResult(BaseModel):
    name: str = ""
    change_type: str = "modified"
    description: str = ""


class FileAnalysisResult(BaseModel):
    path: str = ""
    blocks: list[BlockResult] = Field(default_factory=list)
    doc_update: str = ""
    one_liner: str = ""


class CommitAnalysisResult(BaseModel):
    summary: str = ""
    motivation: str = "原因未知（证据不足）"
    evidence_source: str = "未知"
    risk_level: str = "低"
    files: list[FileAnalysisResult] = Field(default_factory=list)


class EvolutionResult(BaseModel):
    evolution_line: str = ""


def parse_llm_json(model: type[BaseModel], data: Any) -> BaseModel:
    """容错解析：只保留模型声明的字段，缺失用默认值。"""
    if not isinstance(data, dict):
        return model()
    allowed = set(model.model_fields.keys())
    return model(**{k: v for k, v in data.items() if k in allowed})
