"""需求/缺陷追溯 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.deps import get_current_user, get_db
from ...core.errors import NotFoundError
from ...repositories import knowledge_repo as kr
from ...services import issue_service

router = APIRouter(tags=["需求缺陷追溯"])


class RelinkPayload(BaseModel):
    use_llm: bool = False


class ReviewPayload(BaseModel):
    action: str  # confirm | reject


@router.get("/repositories/{repo_id}/issues")
def list_issues(repo_id: int, q: str = "", issue_type: str = "", status: str = "",
                assessment: str = "", user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": kr.list_issues(db, repo_id, q, issue_type, status, assessment)}


@router.post("/repositories/{repo_id}/issues", status_code=201)
def create_issue(repo_id: int, payload: dict,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.create_issue(db, repo_id, payload)


class ImportPayload(BaseModel):
    csv_text: str
    source: str = "csv"


@router.post("/repositories/{repo_id}/issues/import")
def import_issues(repo_id: int, payload: ImportPayload,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.import_issues(db, repo_id, payload.csv_text, payload.source)


@router.post("/repositories/{repo_id}/relink")
def relink(repo_id: int, payload: RelinkPayload | None = None,
           user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = payload or RelinkPayload()
    return issue_service.relink(db, repo_id, p.use_llm)


@router.get("/repositories/{repo_id}/issue-links")
def issue_links(repo_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"groups": kr.issue_links_by_commit(db, repo_id)}


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return kr.issue_detail(db, issue_id)


@router.put("/issues/{issue_id}")
def update_issue(issue_id: int, payload: dict,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.update_issue(db, issue_id, payload)


@router.delete("/issues/{issue_id}", status_code=204)
def delete_issue(issue_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    issue_service.delete_issue(db, issue_id)
    return Response(status_code=204)


@router.post("/issue-links/{link_id}/review")
def review_link(link_id: int, payload: ReviewPayload,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.review(db, link_id, payload.action)


@router.post("/issue-links/{link_id}/confirm")
def confirm_link(link_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.review(db, link_id, "confirm")


@router.post("/issue-links/{link_id}/reject")
def reject_link(link_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.review(db, link_id, "reject")
