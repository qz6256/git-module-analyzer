"""通用 Schema：分页、消息响应。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class MessageOut(BaseModel):
    detail: str


class JobOut(BaseModel):
    job_id: str
