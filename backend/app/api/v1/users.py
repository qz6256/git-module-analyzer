"""用户管理 API（管理员）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...core.deps import get_current_admin, get_db
from ...schemas.auth import AssignRolesIn, UserOut, UserUpdateIn
from ...services import auth_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=list[UserOut])
def list_users(_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return auth_service.list_users(db)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdateIn,
                _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return auth_service.update_user(db, user_id, payload.model_dump(exclude_unset=True))


@router.post("/{user_id}/roles", response_model=UserOut)
def assign_roles(user_id: int, payload: AssignRolesIn,
                 _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return auth_service.assign_roles(db, user_id, payload.role_codes)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    auth_service.delete_user(db, user_id)
    return Response(status_code=204)
