"""分析引擎内部共享的工作区路径（从 legacy app/database.py 迁出）。

legacy 中 git_service / analyzer 依赖 database.py 的 REPOS_DIR；新版数据库层
(db/session.py) 不再暴露该常量，故在 analyzers 包内按旧逻辑本地定义：
workspace/repos/<repo_id>。路径锚定到 backend/，与 settings.workspace_dir
的默认值 "./workspace" 保持一致，避免受进程启动目录影响。
"""
from __future__ import annotations

from pathlib import Path

# backend/ 目录（app/analyzers/_paths.py -> parents[2]）
BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = BACKEND_DIR / "workspace"
REPOS_DIR = WORKSPACE_DIR / "repos"

REPOS_DIR.mkdir(parents=True, exist_ok=True)
