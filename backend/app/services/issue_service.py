"""需求/缺陷追溯业务服务：登记 / CSV 导入 / 重跑关联 / 人工复核。

包装 analyzers/issue_linker.py，保持三级关联、四项信号、三档评级、否决不重建。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..analyzers import issue_linker
from ..core.errors import NotFoundError
from ..models.knowledge import Issue
from ..repositories import knowledge_repo as kr
from ..schemas.project import RepositoryOut  # noqa: F401  保持依赖清晰


def create_issue(db: Session, repo_id: int, data: dict) -> dict:
    issue, _created = issue_linker.upsert_issue(db, repo_id, data)
    db.commit()
    # 登记后立即回填关联
    issue_linker.relink_repo(db, repo_id)
    db.commit()
    return kr.issue_detail(db, issue.id)


def import_issues(db: Session, repo_id: int, csv_text: str, source: str = "csv") -> dict:
    result = issue_linker.import_csv(db, repo_id, csv_text, source)
    db.commit()
    issue_linker.relink_repo(db, repo_id)
    db.commit()
    return result


def update_issue(db: Session, issue_id: int, data: dict) -> dict:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise NotFoundError("事项")
    issue, _ = issue_linker.upsert_issue(db, issue.repo_id, {**data, "external_id": issue.external_id})
    db.commit()
    return kr.issue_detail(db, issue_id)


def delete_issue(db: Session, issue_id: int) -> None:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise NotFoundError("事项")
    db.delete(issue)
    db.commit()


def relink(db: Session, repo_id: int, use_llm: bool = False) -> dict:
    result = issue_linker.relink_repo(db, repo_id, use_llm=use_llm)
    db.commit()
    return result


def review(db: Session, link_id: int, action: str) -> dict:
    result = issue_linker.review_link(db, link_id, action)
    db.commit()
    link = kr.get_link(db, link_id)
    return kr.link_payload(link) if link else result
