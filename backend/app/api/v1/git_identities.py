"""Git 身份 API：自动发现的提交作者列表、绑定 / 解绑、手动新增。"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.deps import get_current_admin, get_current_user, get_db
from ...repositories import git_identity_repo
from ...services import git_identity_service

router = APIRouter(prefix="/git-identities", tags=["Git 身份"])


class BindIn(BaseModel):
    user_id: int | None = None


class ManualIn(BaseModel):
    name: str
    email: str = ""
    user_id: int | None = None


@router.get("")
def list_identities(
    bound_only: bool = False,
    _user=Depends(get_current_user), db: Session = Depends(get_db)
):
    return {"items": git_identity_repo.list_identities(db, bound_only=bound_only)}


@router.post("/manual", status_code=201)
def create_manual(payload: ManualIn,
                  _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    row = git_identity_service.create_manual(
        db, payload.name, payload.email, payload.user_id
    )
    return {"id": row.id, "name": row.name, "email": row.email,
            "user_id": row.user_id, "source": row.source}


@router.put("/{identity_id}/bind")
def bind(identity_id: int, payload: BindIn,
         _admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    row = git_identity_repo.bind_user(db, identity_id, payload.user_id)
    if not row:
        from ...core.errors import NotFoundError
        raise NotFoundError("Git 身份")
    db.commit()
    return {"id": row.id, "user_id": row.user_id}


@router.get("/users/{user_id}/commits")
def user_commits(user_id: int, q: str = "", page: int = 1, size: int = 30,
                 _user=Depends(get_current_user), db: Session = Depends(get_db)):
    """查看某系统用户（按其绑定的 Git 身份）的全部提交。"""
    return git_identity_service.commits_for_user(db, user_id, q, page, size)
