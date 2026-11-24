"""仓库管理 API + 初始化/同步任务。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.deps import get_current_user, get_db
from ...core.errors import NotFoundError
from ...schemas.common import JobOut
from ...schemas.project import RepositoryOut, RepositoryUpdateIn
from ...services import analysis_service, project_service

router = APIRouter(tags=["代码仓库"])


class InitPayload(BaseModel):
    history_limit: int = 60
    max_files: int = 300


class SyncPayload(BaseModel):
    branch: str = ""
    force_rebuild: bool = False


@router.get("/projects/{project_id}/repositories", response_model=list[RepositoryOut])
def list_repos(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.list_repositories(db, project_id)


@router.post("/projects/{project_id}/repositories", response_model=RepositoryOut, status_code=201)
def create_repo(project_id: int, payload: dict,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.create_repository(db, project_id, payload)


@router.put("/repositories/{repo_id}", response_model=RepositoryOut)
def update_repo(repo_id: int, payload: RepositoryUpdateIn,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    return project_service.update_repository(db, repo_id, payload.model_dump(exclude_unset=True))


@router.delete("/repositories/{repo_id}", status_code=204)
def delete_repo(repo_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import Response
    project_service.delete_repository(db, repo_id)
    return Response(status_code=204)


@router.post("/repositories/{repo_id}/initialize", response_model=JobOut)
def initialize(repo_id: int, payload: InitPayload | None = None,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = payload or InitPayload()
    return JobOut(job_id=analysis_service.initialize(db, repo_id, p.history_limit, p.max_files))


@router.post("/repositories/{repo_id}/sync", response_model=JobOut)
def sync(repo_id: int, payload: SyncPayload | None = None,
         user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = payload or SyncPayload()
    return JobOut(job_id=analysis_service.incremental_sync(db, repo_id, p.branch, p.force_rebuild))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user=Depends(get_current_user)):
    job = analysis_service.get_job(job_id)
    if not job:
        raise NotFoundError("任务")
    return job
