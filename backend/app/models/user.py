"""用户与权限模型：User / Role / UserRole。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


def _now() -> datetime:
    return datetime.utcnow()


# 内置角色编码
ROLE_ADMIN = "admin"
ROLE_PROJECT_OWNER = "project_owner"
ROLE_DEVELOPER = "developer"
ROLE_VIEWER = "viewer"
ALL_ROLES = (ROLE_ADMIN, ROLE_PROJECT_OWNER, ROLE_DEVELOPER, ROLE_VIEWER)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(500), default="")

    users: Mapped[list["User"]] = relationship(back_populates="roles", secondary=user_roles)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("email", name="uq_user_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300), default="")
    display_name: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | disabled
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    roles: Mapped[list[Role]] = relationship(back_populates="users", secondary=user_roles)
    git_identity: Mapped["GitIdentity | None"] = relationship(back_populates="user", uselist=False)


class GitIdentity(Base):
    """Git 提交身份：提交里的 author 名 + 邮箱，与系统用户一对一绑定。

    - 初始化扫描时从提交里自动抽取并入库（source=auto），供用户管理下拉选择。
    - 管理员也可手动输入（source=manual）。
    - user_id 为空表示尚未绑定任何系统用户。
    """
    __tablename__ = "git_identities"
    __table_args__ = (
        UniqueConstraint("name", "email", name="uq_git_identity_name_email"),
        Index("ix_git_identities_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), default="")
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), default="auto")  # auto | manual
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User | None"] = relationship(back_populates="git_identity")
