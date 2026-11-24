# 架构契约（v2 · 全量重写）

> 本文件是前后端实现的唯一契约（single source of truth）。任何实现细节以本文为准；
> 变更契约必须先改本文再改代码。旧版代码在 `legacy` 分支，仅供追溯。

## 1. 技术栈

| 层 | 选型 | 版本基线 |
|---|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Axios + Element Plus | Node 22 |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 + pydantic-settings | — |
| 认证 | JWT (PyJWT) + passlib[bcrypt] | — |
| 数据库 | SQLite / PostgreSQL / MySQL / Oracle / SQL Server，`DATABASE_URL` 切换 | — |
| 分析引擎 | 复用 `legacy` 的 git/diff/signal/llm/issue_linker/analyzer（会话注入改造） | — |

## 2. 目录结构

```
git-module-analyzer/
├── ARCHITECTURE.md             本契约
├── backend/
│   ├── pyproject.toml          依赖 + 可选 extras
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── .env.example
│   └── app/
│       ├── main.py             FastAPI 装配 / CORS / 路由挂载
│       ├── core/
│       │   ├── config.py       pydantic-settings 读取 DATABASE_URL 等
│       │   ├── security.py     JWT 签发校验 / 密码哈希
│       │   ├── deps.py         会话依赖 / 当前用户 / 角色守卫
│       │   └── errors.py       统一异常 + 响应包装
│       ├── db/
│       │   ├── base.py         DeclarativeBase + JsonType(TypeDecorator)
│       │   └── session.py      create_engine(方言) / SessionLocal / get_db
│       ├── models/
│       │   ├── user.py         User Role Permission(可选)
│       │   ├── project.py      Project ProjectMember Repository
│       │   └── knowledge.py    11 张分析表
│       ├── schemas/
│       │   ├── auth.py  project.py  knowledge.py  common.py
│       ├── repositories/       纯数据访问，输入 db: Session
│       │   ├── user_repo.py  project_repo.py  knowledge_repo.py
│       ├── services/           业务逻辑，注入 repo 与Session
│       │   ├── auth_service.py  project_service.py
│       │   ├── analysis_service.py  issue_service.py  job_service.py
│       ├── analyzers/          从 legacy 迁入，纯逻辑，不 import models/Session
│       │   ├── git_service.py  diff_parser.py  signal_filter.py
│       │   ├── llm_service.py  issue_linker.py  analyzer.py
│       └── api/v1/
│           ├── router.py       汇总挂载
│           ├── auth.py  users.py  projects.py  repositories.py
│           ├── modules.py  files.py  commits.py  issues.py  settings.py
├── frontend/
│   ├── package.json  vite.config.ts  tsconfig.json  index.html
│   └── src/
│       ├── main.ts  App.vue
│       ├── api/           request.ts (axios 封装) + modules/*.ts
│       ├── stores/        auth.ts project.ts ui.ts
│       ├── router/        index.ts (路由守卫)
│       ├── layouts/       MainLayout.vue AuthLayout.vue
│       ├── views/         Login.vue Projects.vue ProjectDetail.vue
│       │                  Modules.vue ModuleDetail.vue Files.vue FileDetail.vue
│       │                  Commits.vue Issues.vue IssueDetail.vue Settings.vue
│       ├── components/    PageHeader.vue StatCard.vue EmptyState.vue 等
│       ├── styles/        tokens.css (深浅双主题) + main.css
│       └── types/         index.ts (与后端 schemas 对齐)
```

## 3. 数据模型

### 3.1 新增：用户与权限

- `users`: id, username(唯一), email(唯一), password_hash, display_name, status(active/disabled), is_superuser, last_login_at, created_at
- `roles`: id, code(唯一: admin/project_owner/developer/viewer), name, description
- `user_roles`: user_id, role_id（联合主键）
- `projects`: id, name, city, department, business_domain, owner_id→users, description, start_date, planned_end_date, status(planning/active/archived), tags(JSON), created_at, updated_at
- `project_members`: project_id, user_id, role_id, joined_at（联合主键 project_id+user_id）
- `repositories`（改造现有表）: 增加 project_id→projects, repo_type(frontend/backend/app/miniprogram/other), display_name；保留 name/source/source_type/local_path/default_branch/branches/status/status_message/last_analyzed_at/created_at

### 3.2 现有 11 张分析表（加归属）

`branch_states`, `project_modules`, `module_change_events`, `module_candidates`, `source_files`,
`file_change_events`, `commit_analyses`, `issues`, `issue_commit_links`, `system_config`

- 凡有 `repo_id` 的表，保持 repo_id 外键；
- 需要项目层汇总的表（project_modules, commit_analyses, issues, issue_commit_links）额外冗余 `project_id` 便于聚合查询（写入时同步冗余）。

### 3.3 跨数据库约定（强制）

1. 主键统一 `Integer, primary_key=True, autoincrement=True`
2. 时间统一 `DateTime, default=datetime.utcnow`（Python 侧），不用 `func.now()`
3. JSON 字段统一用 `app.db.base.JsonType`（TypeDecorator：SQLite/PG/MySQL 用原生 JSON，Oracle/MSSQL 用 Text+序列化）
4. 所有文本字段显式长度 `String(n)`；长文本用 `Text`（Oracle 映射 CLOB 由 SQLAlchemy 处理）
5. 唯一约束、索引名全局唯一且不超 30 字符（Oracle 限制）
6. 禁用 SQLite 专有 SQL；WAL pragma 仅在 `event.listens_for(engine,'connect')` 且方言为 sqlite 时执行

## 4. API 契约（前缀 /api/v1）

统一响应：成功直接返回数据对象；错误返回 `{"detail": "..."}` + HTTP 状态码。
分页返回 `{"items": [...], "total": n, "page": p, "size": s}`。

### 4.1 认证与用户
```
POST   /auth/register         {username,email,password,display_name?}  → 201 UserOut
POST   /auth/login            {username,password} → {access_token,token_type,user}
GET    /auth/me               → UserOut (含 roles)
POST   /auth/refresh          → {access_token}
GET    /users                 [admin] → UserOut[]
PUT    /users/{id}            [admin] → UserOut
DELETE /users/{id}            [admin] → 204
POST   /users/{id}/roles      [admin] {role_codes:[]} → UserOut
```

### 4.2 项目与仓库
```
GET    /projects              ?city=&domain=&status=&keyword= → ProjectOut[] (含 stats)
POST   /projects              [project_owner+] → 201 ProjectOut
GET    /projects/{id}         → ProjectOut (含 members, repositories)
PUT    /projects/{id}         [owner/admin] → ProjectOut
DELETE /projects/{id}         [owner/admin] → 204
GET    /projects/{id}/overview → {module_count,file_count,commit_count,pending_links,recent_activity[],repo_breakdown[]}
GET    /projects/{id}/members → MemberOut[]
POST   /projects/{id}/members [owner/admin] {user_id,role_code} → MemberOut
DELETE /projects/{id}/members/{user_id} → 204
GET    /projects/{id}/repositories → RepositoryOut[]
POST   /projects/{id}/repositories {name,source,repo_type,...} → 201 RepositoryOut
PUT    /repositories/{id}     → RepositoryOut
DELETE /repositories/{id}     → 204
POST   /repositories/{id}/initialize → {job_id}
POST   /repositories/{id}/sync      {branch?} → {job_id}
GET    /jobs/{job_id}         → {status,progress,message,result}
```

### 4.3 分析产物（沿用现有语义）
```
GET    /repositories/{id}/modules  → ModuleOut[]
GET    /modules/{module_id}        → {module,timeline,files}
GET    /repositories/{id}/module-candidates → CandidateOut[]
POST   /module-candidates/{id}/confirm → {file_count}
POST   /module-candidates/{id}/ignore → 200
GET    /repositories/{id}/files    ?q=&module=&risk=&page=&size= → paged
GET    /files/{file_id}            ?branch=&risk=&author= → {file,timeline}
GET    /files/{file_id}/doc        → text/markdown
GET    /repositories/{id}/commits  ?q=&file=&branch=&risk= → CommitOut[]
GET    /repositories/{id}/branches → BranchStateOut[]
GET    /repositories/{id}/issues   ?q=&issue_type=&status=&assessment= → IssueOut[]
POST   /repositories/{id}/issues   → 201 IssueOut
POST   /repositories/{id}/issues/import → {imported,updated}
POST   /repositories/{id}/relink   → {linked,pending}
GET    /issues/{issue_id}         → {issue,links,signals,stats}
PUT    /issues/{issue_id}         → IssueOut
DELETE /issues/{issue_id}         → 204
POST   /issue-links/{link_id}/confirm → LinkOut
POST   /issue-links/{link_id}/reject  → LinkOut
GET    /repositories/{id}/issue-links → 按 commit 分组
```

### 4.4 设置
```
GET/PUT /settings/llm          → 配置（[admin] 可写；API Key 脱敏返回）
POST   /settings/llm/test      → {ok,message}
GET    /settings/database      → {dialect,connected,tables} （不暴露密码）
GET    /health                 → {status,version}
```

## 5. 鉴权规则

- 除 `/auth/register`（可关闭）、`/auth/login`、`/health` 外全部需要 `Authorization: Bearer <token>`
- 角色：`admin` 全局；其余角色在 `project_members` 内生效
- `project_owner`: 管本项目仓库/成员/初始化/同步；`developer`: 初始化/同步/关联复核；`viewer`: 只读
- 前端路由守卫：无 token → /login；角色不足 → 403 页

## 6. 设计原则（继承 legacy，不得违背）

1. 归纳不是罗列；2. 证据不足写「原因未知（证据不足）」不脑补；3. 高信号过滤；
4. 当前态持续维护；5. 结论可纠错（推测可确认/否决，否决不重建）。
6. 追溯链：需求单据(为什么改) → 提交(谁何时改) → 代码块/文件/模块档案(改了什么)。
7. 系统任何地方不输出「已修复/未修复」，只评估证据充分性。
