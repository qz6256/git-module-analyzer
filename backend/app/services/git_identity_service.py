"""Git 身份业务服务：手动建档、按用户查提交。"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError
from ..models.knowledge import CommitAnalysis
from ..repositories import git_identity_repo


def create_manual(db: Session, name: str, email: str, user_id: int | None = None):
    if not name.strip():
        raise ConflictError("Git 用户名不能为空")
    db.commit()
    row = git_identity_repo.create_manual(db, name, email, user_id)
    db.commit()
    return row


def commits_for_user(db: Session, user_id: int, q: str = "",
                     page: int = 1, size: int = 30) -> dict:
    """按用户绑定的 Git 身份（姓名或邮箱）检索跨仓库提交。"""
    emails = git_identity_repo.emails_for_users(db, [user_id])
    names = git_identity_repo.names_for_users(db, [user_id])
    conds = []
    if emails or names:
        parts = [CommitAnalysis.author_email.in_(emails)] if emails else []
        parts += [CommitAnalysis.author.in_(names)] if names else []
        conds.append(or_(*parts))
    else:
        # 未绑定任何 Git 身份时返回空结果，避免误把所有提交都算上
        conds.append(CommitAnalysis.id < 0)
    if q:
        conds.append(or_(
            CommitAnalysis.message.contains(q),
            CommitAnalysis.summary.contains(q),
            CommitAnalysis.commit_sha.contains(q),
        ))
    from sqlalchemy import func
    total = db.scalar(select(func.count()).select_from(CommitAnalysis).where(*conds)) or 0
    rows = db.scalars(
        select(CommitAnalysis).where(*conds)
        .order_by(CommitAnalysis.committed_at.desc().nullslast(), CommitAnalysis.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return {
        "total": total, "page": page, "size": size,
        "items": [{
            "id": c.id, "commit_sha": c.commit_sha, "sha_short": c.commit_sha[:7],
            "repo_id": c.repo_id, "project_id": c.project_id, "branch": c.branch,
            "author": c.author, "author_email": getattr(c, "author_email", ""),
            "committed_at": c.committed_at.isoformat() if c.committed_at else None,
            "message": c.message, "summary": c.summary, "risk_level": c.risk_level,
        } for c in rows],
    }
