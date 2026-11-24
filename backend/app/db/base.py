"""数据库基类与跨方言 JsonType。

JsonType 解决 5 种数据库的 JSON 列差异：
- SQLite / PostgreSQL / MySQL：使用原生 JSON/JSONB 类型，可查询
- Oracle / SQL Server：回退到 Text(CLOB/NVARCHAR)，Python 侧 JSON 序列化
业务模型统一声明 JsonType，无需关心底层方言。
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import String, Text, TypeDecorator
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有模型共享的声明基类。"""


class JsonType(TypeDecorator):
    """跨数据库 JSON 列：原生优先，不支持则 Text + JSON 字符串。"""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB())
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.JSON())
        if dialect.name == "sqlite":
            return dialect.type_descriptor(sqlite.JSON())
        # oracle / mssql 用 Text(CLOB / NVARCHAR)
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if dialect.name in ("postgresql", "mysql", "sqlite"):
            return value
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if dialect.name in ("postgresql", "mysql", "sqlite"):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
        return value

    @property
    def python_type(self):
        return dict | list
