"""统一异常定义与错误响应。"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常基类。"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str = "资源"):
        super().__init__(f"{resource}不存在", 404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "没有权限执行此操作"):
        super().__init__(message, 403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "请先登录"):
        super().__init__(message, 401)


class ConflictError(AppError):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, 409)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
