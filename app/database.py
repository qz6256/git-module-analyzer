"""SQLite 连接、自动建表与默认配置初始化。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
REPOS_DIR = WORKSPACE_DIR / "repos"
DB_PATH = WORKSPACE_DIR / "db.sqlite3"

WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def _ensure_columns(table: str, additions: dict[str, str]) -> None:
    """老库平滑升级：表不存在则跳过（由 create_all 创建），存在则补齐缺失列。"""
    inspector = inspect(engine)
    if not inspector.has_table(table):
        return
    existing = {c["name"] for c in inspector.get_columns(table)}
    for name, ddl in additions.items():
        if name not in existing:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _migrate_legacy_columns() -> None:
    _ensure_columns("project_modules", {
        "one_liner": "TEXT DEFAULT ''",
        "current_doc": "TEXT DEFAULT ''",
        "evolution_line": "TEXT DEFAULT ''",
        "status": "VARCHAR(20) DEFAULT 'active'",
        "last_commit_sha": "VARCHAR(64) DEFAULT ''",
        "change_count": "INTEGER DEFAULT 0",
    })
    _ensure_columns("issues", {
        "external_url": "TEXT DEFAULT ''", "reporter": "VARCHAR(200) DEFAULT ''",
        "keywords": "JSON", "related_paths": "JSON", "occurred_at": "DATETIME",
    })
    _ensure_columns("issue_commit_links", {
        "assessment_note": "TEXT DEFAULT ''", "llm_note": "TEXT DEFAULT ''",
        "branch": "VARCHAR(200) DEFAULT ''", "decided_at": "DATETIME",
    })


def init_db() -> None:
    """建表并写入默认 LLM 配置（兼容 .env 默认值）。"""
    from . import models  # noqa: F401  确保模型注册
    from .models import SystemConfig

    Base.metadata.create_all(engine)
    _migrate_legacy_columns()
    with SessionLocal() as db:
        row = db.get(SystemConfig, 1)
        if row is None:
            row = SystemConfig(
                id=1,
                base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
                api_key=os.getenv("LLM_API_KEY", ""),
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                max_diff_chars=int(os.getenv("LLM_MAX_DIFF_CHARS", "12000")),
                commit_web_base_url=os.getenv("COMMIT_WEB_BASE_URL", ""),
                llm_enabled=os.getenv("LLM_ENABLED", "1") not in ("0", "false", "False"),
            )
            db.add(row)
            db.commit()


@contextmanager
def session_scope():
    """给后台线程使用的会话上下文。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI 依赖注入。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
