"""新一代一键启动脚本：后端 API + 前端 Vue 开发服务器。

用法：
    python run.py                 # 同时启动后端(8777)与前端(5173)
    python run.py --api-only      # 只启动后端
    python run.py --web-only      # 只启动前端（需先 npm install）
    python run.py --port 9000     # 自定义后端端口
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
# Windows 下 npm 是 npm.cmd，Python subprocess 默认不会按 PATHEXT 补全
NPM = "npm.cmd" if os.name == "nt" else "npm"


def ensure_db() -> None:
    """首次运行用 Alembic 建库（幂等）。"""
    print("[setup] 检查数据库结构 ...")
    alembic = Path(sys.executable).parent / "Scripts" / "alembic.exe"
    cmd = ([str(alembic), "upgrade", "head"] if alembic.exists()
           else [sys.executable, "-m", "alembic", "upgrade", "head"])
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    r = subprocess.run(cmd, cwd=BACKEND, env=env)
    if r.returncode != 0:
        print("[setup] 数据库迁移失败，请检查 DATABASE_URL")
        sys.exit(r.returncode)
    print("[setup] 数据库就绪")


def run_api(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--reload"],
        cwd=BACKEND, env=env,
    )


def run_web() -> subprocess.Popen | None:
    if not (FRONTEND / "node_modules").exists():
        print("[web] 未安装依赖，先执行 npm install ...")
        r = subprocess.run([NPM, "install", "--registry=https://registry.npmmirror.com"], cwd=FRONTEND)
        if r.returncode != 0:
            print("[web] npm install 失败")
            return None
    return subprocess.Popen([NPM, "run", "dev"], cwd=FRONTEND)


def main() -> None:
    parser = argparse.ArgumentParser(description="代码变更历史知识库一键启动")
    parser.add_argument("--port", type=int, default=8777, help="后端端口（默认 8777）")
    parser.add_argument("--api-only", action="store_true", help="只启动后端")
    parser.add_argument("--web-only", action="store_true", help="只启动前端")
    args = parser.parse_args()

    procs: list[subprocess.Popen] = []
    try:
        if not args.web_only:
            ensure_db()
            print(f"[api] 启动后端 http://127.0.0.1:{args.port}  (文档 /docs)")
            procs.append(run_api(args.port))
        if not args.api_only:
            print("[web] 启动前端 http://127.0.0.1:5173")
            web = run_web()
            if web:
                procs.append(web)
        if procs:
            for p in procs:
                p.wait()
    except KeyboardInterrupt:
        print("\n[stop] 正在停止服务 ...")
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
