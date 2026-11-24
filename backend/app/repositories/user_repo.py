"""用户与角色数据访问层。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.errors import ConflictError, NotFoundError
from ..models.user import ALL_ROLES, Role, User


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.id)).all())


def get_role_by_code(db: Session, code: str) -> Role | None:
    return db.scalar(select(Role).where(Role.code == code))


def get_user(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id).options(selectinload(User.roles)))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username).options(selectinload(User.roles)))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id).options(selectinload(User.roles))).all())


def create_user(db: Session, username: str, email: str, password_hash: str,
                display_name: str = "", is_superuser: bool = False) -> User:
    if get_user_by_username(db, username):
        raise ConflictError("用户名已存在")
    if get_user_by_email(db, email):
        raise ConflictError("邮箱已存在")
    user = User(username=username, email=email, password_hash=password_hash,
                display_name=display_name or username, is_superuser=is_superuser)
    db.add(user)
    db.flush()
    return user


def set_user_roles(db: Session, user: User, role_codes: list[str]) -> User:
    valid = [c for c in role_codes if c in ALL_ROLES]
    roles = list(db.scalars(select(Role).where(Role.code.in_(valid))).all()) if valid else []
    user.roles = roles
    db.flush()
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    if not user:
        raise NotFoundError("用户")
    db.delete(user)
    db.flush()
