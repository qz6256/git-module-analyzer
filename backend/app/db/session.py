"""数据库引擎与会话工厂。

按 DATABASE_URL 的方言创建引擎：
- SQLite：WAL / 外键 / busy_timeout 通过 connect 事件设置
- MySQL：charset=utf8mb4
- 其他：标准参数
连接池参数仅对非 SQLite 生效（SQLite 用 NullPool 风格避免文件锁）。
"""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import settings


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 文件路径的父目录不存在时自动创建。"""
    if not url.startswith("sqlite"):
        return
    raw = url.split("///", 1)[-1].split("?", 1)[0]
    if not raw or raw == ":memory:":
        return
    p = Path(raw)
    if p.parent and not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)


def _make_engine() -> Engine:
    url = settings.resolved_database_url
    _ensure_sqlite_dir(url)

    kwargs: dict = {"echo": settings.db_echo, "future": True}
    if settings.is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,
        )
    engine = create_engine(url, **kwargs)

    if settings.is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            try:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA busy_timeout=30000")
            finally:
                cur.close()

    return engine


engine = _make_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 请求级会话依赖。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> tuple[bool, str]:
    """连通性自检：返回 (ok, message)，不泄露密码。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, f"{settings.dialect} 连接正常"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"[:300]
