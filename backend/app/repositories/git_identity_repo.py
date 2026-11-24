"""Git 身份仓储：从提交里抽取、去重、统计，供用户绑定与按人检索。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.user import GitIdentity


def upsert_from_commits(db: Session, authors: list[tuple[str, str]]) -> int:
    """批量登记提交作者（name, email）。返回新增数量。已存在则累加计数。"""
    seen: dict[tuple[str, str], int] = {}
    for name, email in authors:
        name = (name or "").strip()[:200]
        email = (email or "").strip()[:200]
        if not name and not email:
            continue
        key = (name, email)
        seen[key] = seen.get(key, 0) + 1
    if not seen:
        return 0

    created = 0
    for (name, email), count in seen.items():
        row = db.scalar(select(GitIdentity).where(
            GitIdentity.name == name, GitIdentity.email == email
        ))
        if row is None:
            db.add(GitIdentity(
                name=name or email, email=email, source="auto",
                commit_count=count, last_seen_at=datetime.utcnow(),
            ))
            created += 1
        else:
            row.commit_count = (row.commit_count or 0) + count
            row.last_seen_at = datetime.utcnow()
    db.flush()
    return created


def list_identities(db: Session, bound_only: bool = False) -> list[dict]:
    stmt = select(GitIdentity)
    if bound_only:
        stmt = stmt.where(GitIdentity.user_id.is_not(None))
    rows = db.scalars(stmt.order_by(GitIdentity.commit_count.desc(), GitIdentity.id)).all()
    return [{
        "id": r.id, "name": r.name, "email": r.email, "user_id": r.user_id,
        "source": r.source, "commit_count": r.commit_count or 0,
        "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
    } for r in rows]


def bind_user(db: Session, identity_id: int, user_id: int | None) -> GitIdentity | None:
    row = db.get(GitIdentity, identity_id)
    if not row:
        return None
    row.user_id = user_id
    db.flush()
    return row


def create_manual(db: Session, name: str, email: str, user_id: int | None = None) -> GitIdentity:
    row = GitIdentity(name=name.strip()[:200], email=email.strip()[:200],
                      source="manual", user_id=user_id, commit_count=0)
    db.add(row)
    db.flush()
    return row


def emails_for_users(db: Session, user_ids: list[int]) -> list[str]:
    """取这些用户绑定的所有 email，用于按人过滤提交。"""
    if not user_ids:
        return []
    rows = db.scalars(select(GitIdentity.email).where(
        GitIdentity.user_id.in_(user_ids), GitIdentity.email != ""
    )).all()
    return [r for r in rows if r]


def names_for_users(db: Session, user_ids: list[int]) -> list[str]:
    if not user_ids:
        return []
    rows = db.scalars(select(GitIdentity.name).where(
        GitIdentity.user_id.in_(user_ids), GitIdentity.name != ""
    )).all()
    return [r for r in rows if r]
