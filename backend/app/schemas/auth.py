"""认证与用户 Schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from .common import PageResponse


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user: "UserOut"


class RoleOut(BaseModel):
    id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class GitIdentityOut(BaseModel):
    id: int
    name: str
    email: str
    source: str
    commit_count: int = 0
    last_seen_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    status: str
    is_superuser: bool
    last_login_at: datetime | None = None
    roles: list[RoleOut] = []
    git_identity: GitIdentityOut | None = None

    model_config = {"from_attributes": True}


class UserUpdateIn(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    status: str | None = None
    password: str | None = None


class AssignRolesIn(BaseModel):
    role_codes: list[str] = Field(default_factory=list)


class RefreshIn(BaseModel):
    refresh_token: str


LoginOut.model_rebuild()
PageResponse[UserOut].model_rebuild()
