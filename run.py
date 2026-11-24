"""一键启动：自动建表、初始化默认配置、启动 Uvicorn 并打开浏览器。

用法：
    python run.py                 # 默认 http://127.0.0.1:8777
    python run.py --port 9000
    python run.py --no-browser
"""
from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


def load_dotenv() -> None:
    """轻量 .env 读取，不额外依赖 python-dotenv 也能工作。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Git 文件变更历史知识库")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    from app.database import init_db, DB_PATH, WORKSPACE_DIR
    init_db()
    print("=" * 62)
    print("  Git 文件变更历史知识库 · 单机本地版")
    print("=" * 62)
    print(f"  访问地址 : http://{args.host}:{args.port}")
    print(f"  数据库   : {DB_PATH}")
    print(f"  工作目录 : {WORKSPACE_DIR}")
    print("  停止服务 : Ctrl+C")
    print("=" * 62)

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port,
                log_level="info", access_log=False)


if __name__ == "__main__":
    main()
