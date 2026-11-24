"""全局配置：所有环境变量集中于此，通过 pydantic-settings 校验。
切换数据库只需改 DATABASE_URL，业务代码零改动。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 支持的主流库方言
Dialect = Literal["sqlite", "postgresql", "mysql", "oracle", "mssql"]

# 各方言的默认端口与驱动，仅用于拼装提示与连通性测试
DEFAULT_PORTS = {
    "sqlite": None,
    "postgresql": 5432,
    "mysql": 3306,
    "oracle": 1521,
    "mssql": 1433,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ---- 数据库 ----
    # 示例：
    #   sqlite:///./workspace/db.sqlite3
    #   postgresql+psycopg://user:pass@host:5432/dbname
    #   mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4
    #   oracle+oracledb://user:pass@host:1521/?service_name=ORCL
    #   mssql+pymssql://user:pass@host:1433/dbname
    database_url: str = "sqlite:///./workspace/db.sqlite3"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800

    # ---- 认证 ----
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 2
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    # ---- 首个管理员（首次启动自动创建） ----
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"
    bootstrap_admin_email: str = "admin@example.com"

    # ---- 注册开关 ----
    allow_registration: bool = False

    # ---- LLM ----
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_max_diff_chars: int = 12000
    llm_enabled: bool = True
    commit_web_base_url: str = ""

    # ---- 分析 ----
    history_limit: int = 60
    max_files: int = 300
    workspace_dir: str = "./workspace"

    # ---- 应用 ----
    app_name: str = "代码变更历史知识库"
    version: str = "2.0.0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("database_url")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL 不能为空")
        return v.strip()

    @property
    def resolved_database_url(self) -> str:
        """SQLite 相对路径解析为基于 backend/ 的绝对路径，确保任意启动目录都能建库。"""
        url = self.database_url
        if not url.startswith("sqlite"):
            return url
        prefix, rest = url.split(":///", 1) if ":///" in url else (url[: url.index("://")+3], "")
        path_part, _, query = rest.partition("?")
        if path_part in (":memory:", "") or path_part.startswith("/"):
            return url
        backend_dir = Path(__file__).resolve().parents[2]
        abs_path = (backend_dir / path_part).resolve()
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        q = f"?{query}" if query else ""
        return f"{prefix}:///{abs_path.as_posix()}{q}"

    @property
    def dialect(self) -> str:
        return self.database_url.split(":", 1)[0].split("+", 1)[0].lower()

    @property
    def is_sqlite(self) -> bool:
        return self.dialect == "sqlite"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
