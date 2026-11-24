"""FastAPI 应用入口：CORS / 异常处理 / 路由挂载 / 启动初始化。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import router as v1_router
from .core.bootstrap import bootstrap
from .core.config import settings
from .core.errors import AppError, app_error_handler
from .db.session import SessionLocal


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with SessionLocal() as db:
        bootstrap(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="代码变更历史知识库 · Vue3 + FastAPI · 多数据库",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.include_router(v1_router)


@app.get("/")
def root():
    return {"name": settings.app_name, "version": settings.version, "docs": "/docs"}
