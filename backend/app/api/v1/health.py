"""Liveness and readiness probes for orchestration."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.redis_client import get_redis
router = APIRouter()


@router.get("")
@router.get("/")
async def health_root() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME}


@router.get("/live")
async def health_live() -> dict:
    return {
        "status": "alive",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def health_ready() -> dict:
    checks: dict = {}
    degraded = False

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "up"
    except Exception as exc:
        checks["postgresql"] = f"down: {exc}"
        degraded = True

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "up"
    except Exception as exc:
        checks["redis"] = f"down: {exc}"
        degraded = True

    try:
        from app.collector.service import get_collector

        stats = get_collector().get_stats()
        checks["collector"] = "up" if stats.get("running") else "waiting"
        if not stats.get("running") and settings.WAZUH_ALERTS_FILE:
            degraded = True
    except Exception as exc:
        checks["collector"] = f"down: {exc}"
        degraded = True

    checks["queue"] = checks.get("redis", "unknown")

    return {
        "status": "degraded" if degraded else "ready",
        "checks": checks,
        "time": datetime.now(timezone.utc).isoformat(),
    }
