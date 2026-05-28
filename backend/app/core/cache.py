"""
Redis-backed caching decorator
Production-grade caching with TTL, invalidation, and compression.
"""

from __future__ import annotations

import functools
import hashlib
import pickle
from typing import Any, Callable, Optional

import structlog

from app.core.redis_client import get_redis

logger = structlog.get_logger()


def _cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate deterministic cache key from function args.
    """

    key_parts = [prefix]

    # Hash args
    if args:
        args_str = str(args)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        key_parts.append(f"args:{args_hash}")

    # Hash kwargs
    if kwargs:
        # Sort kwargs for deterministic hashing
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = str(sorted_kwargs)
        kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
        key_parts.append(f"kwargs:{kwargs_hash}")

    return ":".join(key_parts)


def cached(
    ttl: int = 300,
    prefix: Optional[str] = None,
    skip_none: bool = True,
) -> Callable:
    """
    Redis-backed caching decorator.

    Args:
        ttl: Time-to-live in seconds (default: 5 minutes)
        prefix: Cache key prefix (default: function name)
        skip_none: Don't cache None results (default: True)

    Example:
        @cached(ttl=600, prefix="dashboard")
        async def get_dashboard_summary(db: AsyncSession):
            return await expensive_query(db)
    """

    def decorator(func: Callable) -> Callable:

        cache_prefix = prefix or f"cache:{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:

            # Generate cache key
            key = _cache_key(cache_prefix, *args, **kwargs)

            try:
                redis = await get_redis()

                # Try to get from cache
                cached_value = await redis.get(key)

                if cached_value:
                    try:
                        result = pickle.loads(cached_value.encode("latin1"))

                        await logger.adebug(
                            "cache_hit",
                            key=key,
                            function=func.__name__,
                        )

                        return result

                    except (pickle.PickleError, Exception) as exc:
                        await logger.awarning(
                            "cache_deserialize_error",
                            key=key,
                            error=str(exc),
                        )

            except Exception as exc:
                await logger.awarning(
                    "cache_get_error",
                    key=key,
                    error=str(exc),
                )

            # Cache miss — execute function
            result = await func(*args, **kwargs)

            # Store in cache
            if result is not None or not skip_none:
                try:
                    redis = await get_redis()

                    serialized = pickle.dumps(result).decode("latin1")

                    await redis.setex(key, ttl, serialized)

                    await logger.adebug(
                        "cache_set",
                        key=key,
                        function=func.__name__,
                        ttl=ttl,
                    )

                except Exception as exc:
                    await logger.awarning(
                        "cache_set_error",
                        key=key,
                        error=str(exc),
                    )

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache keys matching pattern.

    Args:
        pattern: Redis key pattern (e.g., "cache:dashboard:*")

    Returns:
        Number of keys deleted

    Example:
        await invalidate_cache("cache:dashboard:*")
    """

    try:
        redis = await get_redis()

        keys = []

        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            deleted = await redis.delete(*keys)

            await logger.ainfo(
                "cache_invalidated",
                pattern=pattern,
                deleted=deleted,
            )

            return deleted

        return 0

    except Exception as exc:
        await logger.aerror(
            "cache_invalidate_error",
            pattern=pattern,
            error=str(exc),
        )

        return 0
