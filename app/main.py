"""FastAPI 应用入口：静态资源、模板、路由挂载、全局异常处理。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Git 文件变更历史知识库", version="1.0.0",
              description="单机本地运行的单文件变更历史知识库", lifespan=lifespan)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["short_sha"] = lambda s: (s or "")[:7]
templates.env.filters["dt"] = lambda d: d.strftime("%Y-%m-%d %H:%M") if d else "—"
templates.env.filters["risk_class"] = lambda r: {"高": "badge-red", "中": "badge-amber",
                                                 "低": "badge-green"}.get(r, "badge-gray")
app.state.templates = templates

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": f"{type(exc).__name__}: {exc}"}, status_code=500)
    return HTMLResponse(f"<h2>页面出错</h2><pre>{exc}</pre><a href='/'>返回概览</a>",
                        status_code=500)


from .routers import api, pages  # noqa: E402

app.include_router(api.router)
app.include_router(pages.router)
