# 代码变更历史知识库 v2

> **Vue 3 + FastAPI + 多数据库 + 用户权限 + 工程项目管理**
>
> 三视角 + 一条追溯链：需求/缺陷 → Git 提交 → 代码块/文件/模块档案。
> 卖的不是变更历史（`git log` 免费给你），而是「这个文件/这块功能为什么是现在这个样子」的答案。

## 核心能力

- **工程项目管理**：一个项目下挂任意多个代码仓库（前端 / 后端 / App / 小程序 / 其他），合成统一视图；项目成员按角色授权。
- **文件视角**：拉出任一文件，看当前职责、跨提交演进主线、每次改动的代码块、文档更新、可回溯的 Git 提交。
- **模块视角**：新建仓库自动冷启动，按目录与共变关系识别功能模块；后续提交累积职责演进；新功能自动冒出候选，人工确认后建档。
- **模块管理**：按项目聚合多仓库模块，查看模块对应文件、源码预览、提交人、提交记录；支持责任人、知识状态与复核管理。
- **需求/缺陷追溯**：登记「为什么改」，自动三级关联提交，四项信号 → 三档证据评级；**只评估证据充分性，绝不输出「已修复/未修复」**。
- **多数据库**：SQLite / PostgreSQL / MySQL / Oracle / SQL Server，改一行 `DATABASE_URL` 即可切换，Alembic 统一迁移。
- **用户与权限**：JWT 登录、bcrypt 密码、4 种角色（管理员 / 项目负责人 / 开发者 / 访客）、项目级鉴权。

## 快速开始

环境：Python 3.11+、Node 18+、Git。

```bash
# 1. 后端依赖（国内建议加 -i https://mirrors.aliyun.com/pypi/simple/）
cd backend
python -m pip install -e .
# 需要其他数据库时再装对应驱动：pip install -e ".[mysql]"  # postgres / oracle / mssql

# 2. 一键启动（自动建库 + 后端 8777 + 前端 5173）
cd ..
python run.py
```

打开 `http://127.0.0.1:5173`，首次启动自动创建管理员 `admin / admin123`（**生产环境请立即修改**）。

只想启动单侧：

```bash
python run.py --api-only     # 仅后端 http://127.0.0.1:8777 （文档 /docs）
python run.py --web-only     # 仅前端 http://127.0.0.1:5173
```

## 切换数据库

1. 复制 `backend/.env.example` 为 `backend/.env`，按需修改 `DATABASE_URL`：

```ini
# SQLite（默认，零配置）
DATABASE_URL=sqlite:///./workspace/db.sqlite3
# PostgreSQL：pip install -e ".[postgres]"
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/kb
# MySQL：pip install -e ".[mysql]"
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/kb?charset=utf8mb4
# Oracle：pip install -e ".[oracle]"
DATABASE_URL=oracle+oracledb://user:pass@localhost:1521/?service_name=ORCL
# SQL Server：pip install -e ".[mssql]"
DATABASE_URL=mssql+pymssql://user:pass@localhost:1433/kb
```

2. 执行迁移：`cd backend && alembic upgrade head`
3. 重启服务即可。业务代码零改动。

跨库兼容由三层保证：`JsonType`（JSON 列在 5 种方言下的统一适配）、显式主键/时间类型、Alembic 迁移。已验证同一套迁移脚本在 SQLite/MySQL/Oracle/PostgreSQL 下均可生成完整建表 SQL。

## 六步跑通

1. 登录 → 项目工作台 → 新建工程项目（填城市/主管部门/业务域）。
2. 项目详情 → 仓库页 → 添加前端 / 后端 / App 等多个仓库（填本地路径或远程地址）。
3. 对仓库执行「初始化扫描」：目录测绘 → 模块聚类 → 文件/模块建档 → 历史高信号提交 → 两条时间线 → 建立分支水位线。
4. 后续改动执行「增量同步」：只分析新提交，代码块级解析，两套时间线增量更新。
5. 「需求与缺陷」登记事项（填相关路径更准）或 CSV 导入 → 自动关联提交 → 看证据矩阵 → 确认/否决推测关联。
6. 模块 / 文件 / 提交页反向显示关联事项，点击跳回需求单。

未配 LLM 也能完整跑通（本地规则降级）；配置 OpenAI 兼容网关可提升归纳质量。

## 设计边界（不做什么）

不是项目管理工具：不做任务分配、工时、看板、迭代规划。不判断 bug 是否真的修好，只评估可验证证据的充分性。系统任何地方不输出「已修复/未修复」。

## 架构与文档

- `ARCHITECTURE.md`：前后端唯一契约（目录结构、数据模型、API、鉴权、设计原则）。
- `backend/`：分层后端 `core / db / models / schemas / repositories / services / analyzers / api/v1`。分析引擎在 `analyzers/`（`legacy` 分支为旧版实现）。
- `frontend/`：Vue 3 + Vite + TS + Pinia + Router + Element Plus。
- 旧版单体实现保存在 `legacy` 分支，仅供追溯。

## 目录结构

```
git-module-analyzer/
├── ARCHITECTURE.md         架构契约
├── run.py                  一键启动（建库 + 前后端）
├── backend/
│   ├── alembic/            数据库迁移（多方言）
│   └── app/
│       ├── core/           config / security / deps / errors / bootstrap
│       ├── db/             base(JsonType) / session(方言适配)
│       ├── models/         user / project / knowledge
│       ├── schemas/        auth / project / llm / common
│       ├── repositories/   user / project / knowledge
│       ├── services/       auth / project / analysis / issue
│       ├── analyzers/      迁移自 legacy 的纯分析逻辑
│       └── api/v1/         auth / users / projects / repositories / analysis / issues / settings
└── frontend/
    └── src/                api / stores / router / layouts / views / components / styles / types
```

## API 速查

完整契约见 `ARCHITECTURE.md` 第 4 节；启动后端后访问 `http://127.0.0.1:8777/docs` 查看交互式 Swagger 文档（47 个路径 / 59 个操作）。

| 分组 | 主要端点（前缀 `/api/v1`） |
|---|---|
| 认证 | `/auth/login` `/auth/me` `/auth/refresh` `/auth/register` |
| 用户 | `/users` `/users/{id}/roles` |
| 项目 | `/projects` `/projects/{id}` `/projects/{id}/overview` `/projects/{id}/members` |
| 仓库 | `/projects/{id}/repositories` `/repositories/{id}/initialize` `/repositories/{id}/sync` `/jobs/{id}` |
| 分析 | `/repositories/{id}/modules` `/projects/{id}/modules` `/files` `/commits` `/modules/{id}` `/modules/{id}/commits` `/files/{id}/source` |
| 追溯 | `/repositories/{id}/issues` `/issues/{id}` `/issue-links/{id}/confirm\|reject` |
| 设置 | `/settings/llm` `/settings/database` `/health` |
