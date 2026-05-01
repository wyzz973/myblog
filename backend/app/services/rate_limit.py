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

from datetime import UTC, datetime

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


async def check_pet(
    redis: Redis,
    *,
    ip: str,
    per_ip_per_min: int,
    per_ip_per_day: int,
    global_per_day: int,
    unlimited: bool = False,
    hard_ceiling_per_day: int = 20000,
) -> str | None:
    """Rate check for pet summon endpoint.

    Returns the name of the first breached layer, or None if all pass.

    Layered behavior:
    - unlimited=False: enforce per_ip_per_min / per_ip_per_day / global_per_day
      (incremented as side effect — see note below).
    - unlimited=True: skip the three layers entirely; only enforce
      hard_ceiling_per_day on a global daily counter so a runaway script
      can't burn the LLM quota.

    Side-effect note: counters are incremented even when a layer breaches.
    Treating "still within window" as the state (not "consumed only on
    success") prevents oscillation across retries.
    """
    today = datetime.now(UTC).strftime("%Y%m%d")

    if unlimited:
        ceiling_key = f"rl:pet:ceiling:{today}"
        pipe = redis.pipeline()
        pipe.incr(ceiling_key)
        pipe.expire(ceiling_key, 86400, nx=True)
        count, _ = await pipe.execute()
        if int(count) > hard_ceiling_per_day:
            return "hard_ceiling"
        return None

    keys = [
        ("per_ip_per_min", f"rl:pet:ip:{ip}:1m", per_ip_per_min, 60),
        ("per_ip_per_day", f"rl:pet:ip:{ip}:1d", per_ip_per_day, 86400),
        ("global_per_day", f"rl:pet:global:{today}", global_per_day, 86400),
    ]
    pipe = redis.pipeline()
    for _, k, _, ttl in keys:
        pipe.incr(k)
        pipe.expire(k, ttl, nx=True)
    results = await pipe.execute()
    counts = [results[0], results[2], results[4]]
    for (label, _, limit, _), count in zip(keys, counts, strict=True):
        if int(count) > limit:
            return label
    return None
