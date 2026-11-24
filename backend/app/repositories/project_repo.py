"""城市项目、成员、仓库数据访问层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core.errors import ConflictError, NotFoundError
from ..models.knowledge import CommitAnalysis, Issue, IssueCommitLink, ProjectModule, SourceFile
from ..models.project import Project, ProjectMember, Repository


# ---------- Project ----------
def list_projects(db: Session, city: str = "", domain: str = "", status: str = "",
                  keyword: str = "") -> list[Project]:
    q = select(Project)
    if city:
        q = q.where(Project.city.contains(city))
    if domain:
        q = q.where(Project.business_domain.contains(domain))
    if status:
        q = q.where(Project.status == status)
    if keyword:
        q = q.where(Project.name.contains(keyword) | Project.code.contains(keyword))
    return list(db.scalars(q.order_by(Project.id.desc())).all())


def get_project(db: Session, project_id: int) -> Project | None:
    return db.scalar(
        select(Project).where(Project.id == project_id)
        .options(selectinload(Project.repositories), selectinload(Project.members))
    )


def create_project(db: Session, data: dict) -> Project:
    if data.get("code"):
        exists = db.scalar(select(Project).where(Project.code == data["code"]))
        if exists:
            raise ConflictError("项目编码已存在")
    project = Project(**data)
    db.add(project)
    db.flush()
    return project


def update_project(db: Session, project: Project, data: dict) -> Project:
    for key, value in data.items():
        if value is not None and hasattr(project, key):
            setattr(project, key, value)
    db.flush()
    return project


def delete_project(db: Session, project_id: int) -> None:
    project = get_project(db, project_id)
    if not project:
        raise NotFoundError("项目")
    db.delete(project)
    db.flush()


def project_stats(db: Session, project_id: int) -> dict:
    """项目层聚合统计：按 project_id 冗余列或 repo 反查。"""
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)
    module_count = db.scalar(
        select(func.count(ProjectModule.id)).where(ProjectModule.project_id == project_id)
    ) or 0
    file_count = db.scalar(
        select(func.count(SourceFile.id)).where(SourceFile.repo_id.in_(repo_ids))
    ) or 0
    commit_count = db.scalar(
        select(func.count(CommitAnalysis.id)).where(CommitAnalysis.project_id == project_id)
    ) or 0
    issue_count = db.scalar(
        select(func.count(Issue.id)).where(Issue.project_id == project_id)
    ) or 0
    pending_links = db.scalar(
        select(func.count(IssueCommitLink.id)).where(
            IssueCommitLink.project_id == project_id,
            IssueCommitLink.review_status == "pending",
        )
    ) or 0
    return {
        "module_count": module_count,
        "file_count": file_count,
        "commit_count": commit_count,
        "pending_links": pending_links,
        "issue_count": issue_count,
    }


# ---------- Members ----------
def list_members(db: Session, project_id: int) -> list[ProjectMember]:
    return list(db.scalars(
        select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.id)
    ).all())


def get_member(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )


def upsert_member(db: Session, project_id: int, user_id: int, role_id: int) -> ProjectMember:
    member = get_member(db, project_id, user_id)
    if member:
        member.role_id = role_id
    else:
        member = ProjectMember(project_id=project_id, user_id=user_id, role_id=role_id)
        db.add(member)
    db.flush()
    return member


def delete_member(db: Session, project_id: int, user_id: int) -> None:
    member = get_member(db, project_id, user_id)
    if not member:
        raise NotFoundError("项目成员")
    db.delete(member)
    db.flush()


# ---------- Repositories ----------
def list_repositories(db: Session, project_id: int) -> list[Repository]:
    return list(db.scalars(
        select(Repository).where(Repository.project_id == project_id).order_by(Repository.id)
    ).all())


def get_repository(db: Session, repo_id: int) -> Repository | None:
    return db.get(Repository, repo_id)


def create_repository(db: Session, project_id: int, data: dict) -> Repository:
    data = {**data, "project_id": project_id}
    repo = Repository(**data)
    db.add(repo)
    db.flush()
    return repo


def update_repository(db: Session, repo: Repository, data: dict) -> Repository:
    for key, value in data.items():
        if value is not None and hasattr(repo, key):
            setattr(repo, key, value)
    db.flush()
    return repo


def delete_repository(db: Session, repo_id: int) -> None:
    repo = get_repository(db, repo_id)
    if not repo:
        raise NotFoundError("仓库")
    db.delete(repo)
    db.flush()


def user_has_project_access(db: Session, user_id: int, project_id: int) -> bool:
    """用户是否是该项目成员（admin 由上层 bypass）。"""
    return get_member(db, project_id, user_id) is not None
