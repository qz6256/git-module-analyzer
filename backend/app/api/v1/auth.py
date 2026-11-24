"""认证 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.deps import get_current_user, get_db
from ...core.errors import ForbiddenError
from ...schemas.auth import LoginIn, LoginOut, RefreshIn, RegisterIn, TokenOut, UserOut
from ...services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    return auth_service.register(
        db, payload.username, payload.email, payload.password,
        payload.display_name, settings.allow_registration,
    )


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    return auth_service.login(db, payload.username, payload.password)


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    return auth_service.refresh(db, payload.refresh_token)


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return auth_service.get_me(user)
