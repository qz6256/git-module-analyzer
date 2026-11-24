"""城市项目与仓库业务服务。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import user_role_codes
from ..core.errors import ConflictError, ForbiddenError, NotFoundError
from ..models.knowledge import CommitAnalysis, ProjectModule, SourceFile
from ..models.project import ProjectMember, Repository
from ..models.user import ROLE_ADMIN, ROLE_PROJECT_OWNER, Role, User
from ..repositories import project_repo as repo
from ..repositories import user_repo
from ..schemas.project import (
    MemberOut, ProjectOut, ProjectOverview, ProjectStats, RecentActivity,
    RepoBreakdown, RepositoryOut,
)


def _project_out(db: Session, project) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.stats = ProjectStats(**repo.project_stats(db, project.id))
    return out


def _check_access(db: Session, user, project_id: int, write: bool = False) -> None:
    """项目级鉴权：admin 全局放行；其余按 project_members 的角色。"""
    codes = user_role_codes(user)
    if ROLE_ADMIN in codes:
        return
    member = repo.get_member(db, project_id, user.id)
    if not member:
        raise ForbiddenError("你不是该项目的成员")
    if write:
        owner = user_repo.get_role_by_code(db, ROLE_PROJECT_OWNER)
        if not owner or member.role_id != owner.id:
            raise ForbiddenError("需要项目负责人权限")


def list_projects(db: Session, user, city: str = "", domain: str = "",
                  status: str = "", keyword: str = "") -> list[ProjectOut]:
    projects = repo.list_projects(db, city, domain, status, keyword)
    if ROLE_ADMIN not in user_role_codes(user):
        my_ids = set(db.scalars(
            select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        ).all())
        projects = [p for p in projects if p.id in my_ids]
    return [_project_out(db, p) for p in projects]


def get_project(db: Session, project_id: int, user) -> ProjectOut:
    _check_access(db, user, project_id)
    project = repo.get_project(db, project_id)
    if not project:
        raise NotFoundError("项目")
    return _project_out(db, project)


def create_project(db: Session, data: dict, user) -> ProjectOut:
    codes = user_role_codes(user)
    if ROLE_ADMIN not in codes and ROLE_PROJECT_OWNER not in codes:
        raise ForbiddenError("只有管理员或项目负责人可以创建项目")
    project = repo.create_project(db, {**data, "owner_id": user.id})
    db.commit()
    return _project_out(db, project)


def update_project(db: Session, project_id: int, data: dict, user) -> ProjectOut:
    _check_access(db, user, project_id, write=True)
    project = repo.get_project(db, project_id)
    if not project:
        raise NotFoundError("项目")
    repo.update_project(db, project, data)
    db.commit()
    return _project_out(db, project)


def delete_project(db: Session, project_id: int, user) -> None:
    _check_access(db, user, project_id, write=True)
    repo.delete_project(db, project_id)
    db.commit()


def project_overview(db: Session, project_id: int) -> ProjectOverview:
    stats = repo.project_stats(db, project_id)
    repos = db.scalars(select(Repository).where(Repository.project_id == project_id)).all()
    breakdown = [RepoBreakdown(
        repo_id=r.id, repo_name=r.display_name or r.name, repo_type=r.repo_type,
        module_count=db.scalar(select(func.count(ProjectModule.id)).where(ProjectModule.repo_id == r.id)) or 0,
        file_count=db.scalar(select(func.count(SourceFile.id)).where(SourceFile.repo_id == r.id)) or 0,
        commit_count=db.scalar(select(func.count(CommitAnalysis.id)).where(CommitAnalysis.repo_id == r.id)) or 0,
    ) for r in repos]

    recent_rows = db.scalars(
        select(CommitAnalysis).where(CommitAnalysis.project_id == project_id)
        .order_by(CommitAnalysis.committed_at.desc().nullslast(), CommitAnalysis.id.desc())
        .limit(10)
    ).all()
    repo_name_map = {r.id: (r.display_name or r.name) for r in repos}
    recent = [RecentActivity(
        commit_sha=c.commit_sha[:7], message=(c.summary or c.message)[:120],
        author=c.author, committed_at=c.committed_at,
        repo_name=repo_name_map.get(c.repo_id, ""),
    ) for c in recent_rows]
    return ProjectOverview(**stats, recent_activity=recent, repo_breakdown=breakdown)


# ---------- 成员 ----------
def list_members(db: Session, project_id: int) -> list[MemberOut]:
    out = []
    for m in repo.list_members(db, project_id):
        role = db.get(Role, m.role_id)
        user = db.get(User, m.user_id)
        d = MemberOut.model_validate(m)
        d.role = {"id": role.id, "code": role.code, "name": role.name} if role else None
        if user:
            d.user = {
                "id": user.id, "username": user.username, "email": user.email,
                "display_name": user.display_name, "status": user.status,
                "is_superuser": user.is_superuser, "last_login_at": user.last_login_at,
                "roles": [],
            }
        out.append(d)
    return out


def add_member(db: Session, project_id: int, user_id: int, role_code: str) -> MemberOut:
    role = user_repo.get_role_by_code(db, role_code)
    if not role:
        raise NotFoundError("角色")
    member = repo.upsert_member(db, project_id, user_id, role.id)
    db.commit()
    return next(m for m in list_members(db, project_id) if m.id == member.id)


def remove_member(db: Session, project_id: int, user_id: int) -> None:
    repo.delete_member(db, project_id, user_id)
    db.commit()


# ---------- 仓库 ----------
def list_repositories(db: Session, project_id: int) -> list[RepositoryOut]:
    return [RepositoryOut.model_validate(r) for r in repo.list_repositories(db, project_id)]


def create_repository(db: Session, project_id: int, data: dict) -> RepositoryOut:
    if data.get("source_type") not in (None, "local", "remote"):
        raise ConflictError("source_type 只能是 local 或 remote")
    r = repo.create_repository(db, project_id, data)
    db.commit()
    return RepositoryOut.model_validate(r)


def update_repository(db: Session, repo_id: int, data: dict) -> RepositoryOut:
    r = repo.get_repository(db, repo_id)
    if not r:
        raise NotFoundError("仓库")
    repo.update_repository(db, r, data)
    db.commit()
    return RepositoryOut.model_validate(r)


def delete_repository(db: Session, repo_id: int) -> None:
    repo.delete_repository(db, repo_id)
    db.commit()
