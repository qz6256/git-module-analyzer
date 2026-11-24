"""认证业务服务。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import ConflictError, ForbiddenError, UnauthorizedError
from ..core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from ..repositories import user_repo as repo
from ..schemas.auth import LoginOut, UserOut


def _to_out(user) -> UserOut:
    return UserOut.model_validate(user)


def register(db: Session, username: str, email: str, password: str,
             display_name: str = "", allow_registration: bool = False) -> UserOut:
    if not allow_registration:
        raise ForbiddenError("注册已关闭，请联系管理员创建账号")
    user = repo.create_user(db, username, email, hash_password(password), display_name)
    viewer = repo.get_role_by_code(db, "viewer")
    if viewer:
        repo.set_user_roles(db, user, ["viewer"])
    db.commit()
    return _to_out(user)


def login(db: Session, username: str, password: str) -> LoginOut:
    user = repo.get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("用户名或密码错误")
    if user.status != "active":
        raise ForbiddenError("账号已禁用")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return LoginOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        user=_to_out(user),
    )


def refresh(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, "refresh")
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc
    user = repo.get_user(db, int(payload["sub"]))
    if not user or user.status != "active":
        raise UnauthorizedError("用户不存在或已禁用")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


def get_me(user) -> UserOut:
    return _to_out(user)


def list_users(db: Session) -> list[UserOut]:
    return [_to_out(u) for u in repo.list_users(db)]


def update_user(db: Session, user_id: int, data: dict) -> UserOut:
    user = repo.get_user(db, user_id)
    if not user:
        raise ConflictError("用户不存在") from None
    for key in ("display_name", "email", "status"):
        if data.get(key) is not None:
            setattr(user, key, data[key])
    if data.get("password"):
        user.password_hash = hash_password(data["password"])
    db.commit()
    return _to_out(user)


def assign_roles(db: Session, user_id: int, role_codes: list[str]) -> UserOut:
    from ..models.user import ROLE_ADMIN
    user = repo.get_user(db, user_id)
    if not user:
        raise ConflictError("用户不存在") from None
    repo.set_user_roles(db, user, role_codes)
    # 同步 superuser 标记，便于全局鉴权
    user.is_superuser = ROLE_ADMIN in role_codes
    db.commit()
    return _to_out(user)


def delete_user(db: Session, user_id: int) -> None:
    repo.delete_user(db, user_id)
    db.commit()
