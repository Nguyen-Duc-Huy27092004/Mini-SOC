"""Operational monitoring: collector, websocket, redis."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.collector.service import get_collector
from app.core.redis_client import get_redis
from app.core.security import require_roles
from app.models.user import User
from app.websocket.manager import manager

router = APIRouter()


@router.get("/stats")
async def platform_stats(
    _: User = Depends(require_roles(["Super Admin", "SOC Analyst", "IT Admin"])),
) -> dict:
    collector = get_collector()
    redis_ok = False
    try:
        redis = await get_redis()
        redis_ok = await redis.ping()
    except Exception:
        redis_ok = False

    return {
        "collector": collector.get_stats(),
        "websocket_connections": len(manager._clients),
        "redis": "up" if redis_ok else "down",
    }
