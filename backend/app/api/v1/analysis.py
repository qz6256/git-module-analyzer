"""分析产物查询 API：模块 / 文件 / 提交 / 分支。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.deps import get_current_user, get_db
from ...repositories import knowledge_repo as kr
from ...services import analysis_service, source_service

router = APIRouter(tags=["分析产物"])


class ModuleUpdateIn(BaseModel):
    module_owner_user_id: int | None = None
    knowledge_status: str | None = None
    review_due_at: datetime | None = None


# ---- 模块 ----
@router.get("/repositories/{repo_id}/modules")
def list_modules(repo_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": kr.list_modules(db, repo_id)}


@router.get("/projects/{project_id}/modules")
def project_modules(project_id: int, user=Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return {"items": kr.project_modules(db, project_id)}


@router.get("/modules/{module_id}")
def module_detail(module_id: int, branch: str = "",
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.module_detail(db, module_id, branch)


@router.put("/modules/{module_id}")
def update_module(module_id: int, payload: ModuleUpdateIn,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.update_module(db, module_id, payload.model_dump(exclude_unset=True))


@router.get("/modules/{module_id}/commits")
def module_commits(module_id: int, page: int = 1, size: int = 30,
                   author: str = "", user_id: int | None = None,
                   branch: str = "", q: str = "",
                   user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.module_commits(db, module_id, page, size, author, user_id, branch, q)


@router.get("/repositories/{repo_id}/module-candidates")
def list_candidates(repo_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": kr.list_module_candidates(db, repo_id)}


@router.post("/module-candidates/{candidate_id}/confirm")
def confirm_candidate(candidate_id: int, payload: dict | None = None,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_service.confirm_candidate(db, candidate_id, (payload or {}).get("name", ""))


@router.post("/module-candidates/{candidate_id}/ignore")
def ignore_candidate(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_service.ignore_candidate(db, candidate_id)


# ---- 文件 ----
@router.get("/repositories/{repo_id}/files")
def list_files(repo_id: int, q: str = "", module: str = "", risk: str = "",
               page: int = 1, size: int = 30,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.list_files(db, repo_id, q, module, risk, page, size)


@router.get("/files/{file_id}")
def file_detail(file_id: int, branch: str = "", risk: str = "", author: str = "",
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.file_detail(db, file_id, branch, risk, author)


@router.get("/files/{file_id}/doc")
def file_doc(file_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.file_doc(db, file_id)


@router.get("/files/{file_id}/source")
def file_source(file_id: int, branch: str = "",
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    return source_service.read_source(db, file_id, branch)


# ---- 提交 ----
@router.get("/repositories/{repo_id}/commits")
def list_commits(repo_id: int, q: str = "", branch: str = "", risk: str = "",
                 author: str = "", file: str = "", only_high: str = "",
                 page: int = 1, size: int = 30, user_id: int | None = None,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.list_commits(db, repo_id, q, branch, risk, author, file,
                           only_high == "1", page, size, user_id=user_id)


@router.get("/repositories/{repo_id}/branches")
def list_branches(repo_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": kr.list_branches(db, repo_id)}
