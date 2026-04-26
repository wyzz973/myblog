from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

_settings = get_settings()
_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(_settings.redis_url, decode_responses=True)
    return _pool


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_get_pool())


async def ping() -> bool:
    client = get_redis()
    try:
        return await client.ping()
    finally:
        await client.aclose()
