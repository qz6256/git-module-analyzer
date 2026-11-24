"""v1 路由汇总：前缀 /api/v1。"""
from __future__ import annotations

from fastapi import APIRouter

from . import analysis, auth, issues, projects, repositories, settings, users

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(projects.router)
router.include_router(repositories.router)
router.include_router(analysis.router)
router.include_router(issues.router)
router.include_router(settings.router)
