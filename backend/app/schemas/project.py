"""工程项目与仓库 Schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .auth import RoleOut, UserOut


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = ""
    city: str = ""
    department: str = ""
    business_domain: str = ""
    description: str = ""
    start_date: datetime | None = None
    planned_end_date: datetime | None = None
    status: str = "active"
    tags: list[str] = Field(default_factory=list)


class ProjectCreateIn(ProjectBase):
    pass


class ProjectUpdateIn(BaseModel):
    name: str | None = None
    code: str | None = None
    city: str | None = None
    department: str | None = None
    business_domain: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    planned_end_date: datetime | None = None
    status: str | None = None
    tags: list[str] | None = None
    owner_id: int | None = None


class ProjectStats(BaseModel):
    module_count: int = 0
    file_count: int = 0
    commit_count: int = 0
    pending_links: int = 0
    issue_count: int = 0


class ProjectOut(BaseModel):
    id: int
    name: str
    code: str
    city: str
    department: str
    business_domain: str
    description: str
    status: str
    tags: list[str] = []
    owner_id: int | None = None
    created_at: datetime
    updated_at: datetime
    stats: ProjectStats = Field(default_factory=ProjectStats)

    model_config = {"from_attributes": True}


class RepositoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    display_name: str = ""
    repo_type: str = "backend"
    source: str
    source_type: str = "local"
    local_path: str = ""
    default_branch: str = "main"
    branches: list[str] = Field(default_factory=list)
    # Git 凭据：auth_type = none | token | password | ssh_key
    auth_type: str = "none"
    credential: str = ""  # 明文输入，仅用于加密后入库，不会回显


class RepositoryCreateIn(RepositoryBase):
    pass


class RepositoryUpdateIn(BaseModel):
    name: str | None = None
    display_name: str | None = None
    repo_type: str | None = None
    source: str | None = None
    default_branch: str | None = None
    branches: list[str] | None = None
    auth_type: str | None = None
    credential: str | None = None  # 传空串表示清空凭据


class RepositoryOut(BaseModel):
    id: int
    project_id: int
    name: str
    display_name: str
    repo_type: str
    source: str
    source_type: str
    local_path: str
    default_branch: str
    branches: list[str] = []
    auth_type: str = "none"
    has_credential: bool = False
    status: str
    status_message: str
    last_analyzed_at: datetime | None = None
    created_at: datetime
    init_job_id: str | None = None

    model_config = {"from_attributes": True}


class MemberIn(BaseModel):
    user_id: int
    role_code: str


class MemberOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    role_id: int
    role: RoleOut | None = None
    user: UserOut | None = None
    joined_at: datetime

    model_config = {"from_attributes": True}


class RecentActivity(BaseModel):
    commit_sha: str
    message: str
    author: str
    committed_at: datetime | None = None
    repo_name: str = ""


class RepoBreakdown(BaseModel):
    repo_id: int
    repo_name: str
    repo_type: str
    module_count: int = 0
    file_count: int = 0
    commit_count: int = 0


class ProjectOverview(BaseModel):
    module_count: int = 0
    file_count: int = 0
    commit_count: int = 0
    pending_links: int = 0
    issue_count: int = 0
    recent_activity: list[RecentActivity] = []
    repo_breakdown: list[RepoBreakdown] = []
