"""城市项目 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...core.deps import get_current_user, get_db
from ...schemas.project import (
    MemberIn, MemberOut, ProjectOut, ProjectUpdateIn, ProjectOverview,
)
from ...services import project_service

router = APIRouter(prefix="/projects", tags=["城市项目"])


@router.get("", response_model=list[ProjectOut])
def list_projects(city: str = "", domain: str = "", status: str = "", keyword: str = "",
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.list_projects(db, user, city, domain, status, keyword)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.create_project(db, payload, user)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.get_project(db, project_id, user)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdateIn,
                   user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.update_project(db, project_id, payload.model_dump(exclude_unset=True), user)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    project_service.delete_project(db, project_id, user)
    return Response(status_code=204)


@router.get("/{project_id}/overview", response_model=ProjectOverview)
def project_overview(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.project_overview(db, project_id)


# ---------- 成员 ----------
@router.get("/{project_id}/members", response_model=list[MemberOut])
def list_members(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.list_members(db, project_id)


@router.post("/{project_id}/members", response_model=MemberOut, status_code=201)
def add_member(project_id: int, payload: MemberIn,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.add_member(db, project_id, payload.user_id, payload.role_code)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: int, user_id: int,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    project_service.remove_member(db, project_id, user_id)
    return Response(status_code=204)
