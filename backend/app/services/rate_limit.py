"""Redis-backed rate limiter.

Two primitives:

    hit(key, limit, window_sec)
        Atomic INCR + EXPIRE-NX. Raises RateLimited when count > limit.

    mark_failure / reset_failures / lockout_active
        Lockout pattern for credential endpoints: count failures in a
        rolling window, set a separate lock key after threshold.

Keys are colon-separated and namespaced by caller (e.g. 'rl:login:1.2.3.4').
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.errors import RateLimited

LOCK_PREFIX = "rl:lock:"
FAIL_PREFIX = "rl:fail:"


async def hit(redis: Redis, key: str, *, limit: int, window_sec: int) -> None:
    """Increment counter; raise RateLimited if over limit."""
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_sec, nx=True)
    count, _ = await pipe.execute()
    if count > limit:
        ttl = await redis.ttl(key)
        raise RateLimited(retry_after=max(int(ttl), 1))


async def mark_failure(
    redis: Redis,
    subject: str,
    *,
    threshold: int,
    lock_window_sec: int,
) -> int:
    """Increment failure counter; on threshold, set lock key. Returns count."""
    fail_key = f"{FAIL_PREFIX}{subject}"
    pipe = redis.pipeline()
    pipe.incr(fail_key)
    pipe.expire(fail_key, lock_window_sec, nx=True)
    count, _ = await pipe.execute()
    if count >= threshold:
        await redis.set(f"{LOCK_PREFIX}{subject}", "1", ex=lock_window_sec)
    return int(count)


async def reset_failures(redis: Redis, subject: str) -> None:
    """Clear failure counter (e.g. on successful login)."""
    await redis.delete(f"{FAIL_PREFIX}{subject}")


async def lockout_active(redis: Redis, subject: str) -> bool:
    return bool(await redis.exists(f"{LOCK_PREFIX}{subject}"))


async def lockout_retry_after(redis: Redis, subject: str) -> int:
    ttl = await redis.ttl(f"{LOCK_PREFIX}{subject}")
    return max(int(ttl), 1) if ttl and ttl > 0 else 60
