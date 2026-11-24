"""模型注册中心：导入全部模型供 Alembic autogenerate 与建表使用。"""
from ..db.base import Base  # noqa: F401
from .user import Role, User, user_roles  # noqa: F401
from .project import Project, ProjectMember, Repository  # noqa: F401
from .knowledge import (  # noqa: F401
    SystemConfig, BranchState, ProjectModule, ModuleChangeEvent,
    ModuleCandidate, SourceFile, FileChangeEvent, CommitAnalysis,
    Issue, IssueCommitLink,
)
