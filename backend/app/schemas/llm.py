"""LLM 结构化输出校验模型（从 legacy schemas.py 迁出）。

analyzers/llm_service.py 依赖这些模型做结构化解析与降级。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
