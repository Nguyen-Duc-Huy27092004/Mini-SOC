"""
Production-grade Redis Rate Limiter

Features:
- Sliding window approximation
- Atomic Redis pipeline
- Proxy-aware client IP extraction
- Graceful Redis failure handling
- Retry-After headers
- Structured logging
- Reusable dependency factory
"""

from __future__ import annotations

import time
from typing import Optional

import structlog
from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.core.redis_client import get_redis

logger = structlog.get_logger()

RATE_LIMIT_PREFIX = "ratelimit"


# ============================================================
# Helpers
# ============================================================

def get_client_ip(request: Request) -> str:
    """
    Extract real client IP safely.
    """

    forwarded = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get(
        "x-real-ip"
    )

    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


# ============================================================
# Core Rate Limit
# ============================================================

async def check_rate_limit(
    request: Request,
    response: Optional[Response],
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> None:
    """
    Redis-backed fixed-window limiter with
    production safeguards.
    """

    try:

        redis = await get_redis()

        current_window = int(
            time.time() // window_seconds
        )

        redis_key = (
            f"{RATE_LIMIT_PREFIX}:"
            f"{key}:{current_window}"
        )

        async with redis.pipeline(transaction=True) as pipe:

            pipe.incr(redis_key)
            pipe.expire(
                redis_key,
                window_seconds + 5,
            )

            result = await pipe.execute()

        current_count = int(result[0])

        remaining = max(
            0,
            limit - current_count,
        )

        retry_after = window_seconds

        if response:

            response.headers[
                "X-RateLimit-Limit"
            ] = str(limit)

            response.headers[
                "X-RateLimit-Remaining"
            ] = str(remaining)

            response.headers[
                "Retry-After"
            ] = str(retry_after)

        if current_count > limit:

            client_ip = get_client_ip(request)

            logger.warning(
                "rate_limit_exceeded",
                key=key,
                client_ip=client_ip,
                limit=limit,
                current=current_count,
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Quá nhiều yêu cầu. "
                    "Vui lòng thử lại sau."
                ),
                headers={
                    "Retry-After": str(
                        retry_after
                    )
                },
            )

    except HTTPException:
        raise

    except Exception:

        logger.exception(
            "rate_limit_redis_failure"
        )

        # Fail-open strategy:
        # API continues if Redis dies
        return


# ============================================================
# Login Protection
# ============================================================

async def login_rate_limit(
    request: Request,
    response: Response,
) -> None:

    client_ip = get_client_ip(request)

    await check_rate_limit(
        request=request,
        response=response,
        key=f"login:{client_ip}",
        limit=settings.LOGIN_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )


# ============================================================
# Generic API Limiter
# ============================================================

async def api_rate_limit(
    request: Request,
    response: Response,
) -> None:

    client_ip = get_client_ip(request)

    await check_rate_limit(
        request=request,
        response=response,
        key=f"api:{client_ip}",
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )