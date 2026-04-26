"""Async redis client + FastAPI dependency."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from redis.asyncio import Redis, from_url

from app.config import get_settings

_client: Redis | None = None
_init_lock = asyncio.Lock()


async def get_redis() -> AsyncIterator[Redis]:
    """FastAPI dependency yielding a process-wide Redis connection."""
    global _client
    if _client is None:
        async with _init_lock:
            if _client is None:
                _client = from_url(get_settings().redis_url, decode_responses=True)
    yield _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
