from __future__ import annotations

from app.core.redis_client import get_redis


class RedisManager:
    def __init__(self) -> None:
        self._redis = None

    async def initialize(self):
        self._redis = await get_redis()
        return self._redis

    @property
    def client(self):
        return self._redis


def get_redis_manager() -> RedisManager:
    return RedisManager()
