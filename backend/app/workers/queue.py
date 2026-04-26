"""ARQ enqueue helper with inline mode for tests."""
from __future__ import annotations

from typing import Any

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.config import get_settings
from app.workers import tasks as task_mod

_pool: ArqRedis | None = None
_TASK_REGISTRY: dict[str, Any] = {}


def register(name: str, fn: Any) -> None:
    """Called from runner.py to register tasks for both ARQ and inline mode."""
    _TASK_REGISTRY[name] = fn


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue(name: str, **kwargs: Any) -> str:
    """Enqueue a registered task. In inline mode, runs synchronously and
    returns 'inline'. Otherwise pushes to Redis and returns the job_id."""
    settings = get_settings()
    if settings.arq_inline:
        fn = _TASK_REGISTRY.get(name)
        if fn is None:
            raise RuntimeError(f"task {name!r} not registered")
        await fn({}, **kwargs)
        return "inline"
    pool = await _get_pool()
    job = await pool.enqueue_job(name, **kwargs)
    return job.job_id if job else ""


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
