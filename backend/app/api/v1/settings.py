"""系统设置 API：LLM 配置 / 数据库状态 / 健康检查。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.deps import get_current_admin, get_current_user, get_db
from ...db.session import check_connection
from ...models.knowledge import SystemConfig

router = APIRouter(tags=["系统设置"])


class LLMConfigIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    max_diff_chars: int = 12000
    commit_web_base_url: str = ""
    llm_enabled: bool = True


def _mask(key: str) -> str:
    return f"{key[:4]}***" if key and len(key) > 8 else ("***" if key else "")


@router.get("/settings/llm")
def get_llm_config(_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    cfg = db.get(SystemConfig, 1)
    if not cfg:
        return {}
    return {
        "base_url": cfg.base_url, "api_key": _mask(cfg.api_key), "model": cfg.model,
        "max_diff_chars": cfg.max_diff_chars,
        "commit_web_base_url": cfg.commit_web_base_url, "llm_enabled": cfg.llm_enabled,
    }


@router.put("/settings/llm")
def update_llm_config(payload: LLMConfigIn, _admin=Depends(get_current_admin),
                      db: Session = Depends(get_db)):
    cfg = db.get(SystemConfig, 1)
    if not cfg:
        cfg = SystemConfig(id=1)
        db.add(cfg)
    data = payload.model_dump()
    # 前端传来脱敏值时保留原 key
    if data["api_key"] and "***" in data["api_key"]:
        data.pop("api_key")
    for key, value in data.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    db.commit()
    return {"ok": True}


@router.post("/settings/llm/test")
def test_llm(_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    from ...analyzers import llm_service
    cfg = llm_service.get_config(db)
    ok, message = llm_service.test_connection(cfg)
    return {"ok": ok, "message": message}


@router.get("/settings/database")
def database_status(_admin=Depends(get_current_admin)):
    ok, message = check_connection()
    return {"dialect": settings.dialect, "connected": ok, "message": message}


@router.get("/health")
def health():
    return {"status": "ok", "version": settings.version}
