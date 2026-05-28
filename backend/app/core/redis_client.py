"""
Shared Redis Connection Pool
Production-ready async Redis manager for:
- Sessions
- Rate limiting
- Pub/Sub
- WebSocket fan-out
"""

from __future__ import annotations

import asyncio
from typing import Optional

import redis.asyncio as aioredis
import structlog
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from app.core.config import settings

logger = structlog.get_logger()

# =========================================================
# Globals
# =========================================================

_redis: Optional[aioredis.Redis] = None
_pool: Optional[ConnectionPool] = None

# =========================================================
# Redis Factory
# =========================================================

async def _create_redis() -> aioredis.Redis:
    """
    Create and validate Redis connection.
    """

    global _pool

    _pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=100,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )

    redis = aioredis.Redis(connection_pool=_pool)

    # Validate connection immediately
    await redis.ping()

    await logger.ainfo(
        "redis_connected",
        url=settings.REDIS_URL,
    )

    return redis


# =========================================================
# Public Accessor
# =========================================================

async def get_redis() -> aioredis.Redis:
    """
    Return shared Redis client.

    Auto-recovers from dropped connections.
    """

    global _redis

    if _redis is None:
        try:
            _redis = await _create_redis()

        except Exception:
            await logger.aerror(
                "redis_initial_connection_failed",
                exc_info=True,
            )
            raise

    # Health check existing connection
    try:
        await _redis.ping()

    except RedisError:
        await logger.awarning(
            "redis_connection_lost_reconnecting"
        )

        try:
            await close_redis()
            _redis = await _create_redis()

        except Exception:
            await logger.aerror(
                "redis_reconnect_failed",
                exc_info=True,
            )
            raise

    return _redis


# =========================================================
# Graceful Shutdown
# =========================================================

async def close_redis() -> None:
    """
    Close Redis connections gracefully.
    """

    global _redis
    global _pool

    try:
        if _redis is not None:
            await _redis.aclose()
            _redis = None

        if _pool is not None:
            await _pool.aclose()
            _pool = None

        await logger.ainfo("redis_closed")

    except Exception:
        await logger.aerror(
            "redis_close_error",
            exc_info=True,
        )


# =========================================================
# Healthcheck
# =========================================================

async def redis_healthcheck() -> bool:
    """
    Lightweight Redis healthcheck.
    """

    try:
        redis = await get_redis()

        result = await redis.ping()

        return result is True

    except Exception:
        return False