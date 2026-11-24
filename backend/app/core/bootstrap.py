"""首次启动初始化：内置角色、bootstrap 管理员、默认 LLM 配置。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.knowledge import SystemConfig
from ..models.user import ALL_ROLES, ROLE_ADMIN, Role, User
from .config import settings
from .security import hash_password

ROLE_NAMES = {
    "admin": "系统管理员",
    "project_owner": "项目负责人",
    "developer": "开发者",
    "viewer": "访客",
}


def bootstrap(db: Session) -> None:
    """幂等初始化，可重复调用。"""
    # 1. 内置角色
    for code in ALL_ROLES:
        if db.scalar(select(Role).where(Role.code == code)) is None:
            db.add(Role(code=code, name=ROLE_NAMES.get(code, code), description=""))
    db.flush()

    # 2. bootstrap 管理员
    admin = db.scalar(select(User).where(User.username == settings.bootstrap_admin_username))
    if admin is None:
        admin = User(
            username=settings.bootstrap_admin_username,
            email=settings.bootstrap_admin_email,
            password_hash=hash_password(settings.bootstrap_admin_password),
            display_name="系统管理员",
            is_superuser=True,
        )
        admin_role = db.scalar(select(Role).where(Role.code == ROLE_ADMIN))
        if admin_role:
            admin.roles.append(admin_role)
        db.add(admin)
        db.flush()

    # 3. 默认 LLM 配置
    if db.get(SystemConfig, 1) is None:
        db.add(SystemConfig(
            id=1,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            max_diff_chars=settings.llm_max_diff_chars,
            commit_web_base_url=settings.commit_web_base_url,
            llm_enabled=settings.llm_enabled,
        ))

    db.commit()
