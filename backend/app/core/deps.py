"""依赖注入：数据库会话、当前用户、角色守卫、项目权限。"""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db.session import get_db as _get_db
from ..models.user import ROLE_ADMIN, User
from .security import decode_token

get_db = _get_db


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer token 解析当前用户。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, "access")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser and ROLE_ADMIN not in [r.code for r in user.roles]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def user_role_codes(user: User) -> set[str]:
    return {r.code for r in user.roles} | ({"admin"} if user.is_superuser else set())
