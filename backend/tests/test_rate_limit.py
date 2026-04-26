import asyncio

import pytest

from app.errors import RateLimited
from app.services.rate_limit import hit, lockout_active, mark_failure, reset_failures


async def test_hit_under_limit_no_raise(redis):
    for _ in range(5):
        await hit(redis, "k:test1", limit=5, window_sec=60)


async def test_hit_over_limit_raises(redis):
    for _ in range(3):
        await hit(redis, "k:test2", limit=3, window_sec=60)
    with pytest.raises(RateLimited) as exc:
        await hit(redis, "k:test2", limit=3, window_sec=60)
    assert exc.value.retry_after >= 1


async def test_hit_keys_independent(redis):
    for _ in range(5):
        await hit(redis, "k:a", limit=5, window_sec=60)
    # k:b is fresh
    await hit(redis, "k:b", limit=5, window_sec=60)


async def test_window_expires(redis):
    await hit(redis, "k:exp", limit=1, window_sec=1)
    with pytest.raises(RateLimited):
        await hit(redis, "k:exp", limit=1, window_sec=1)
    await asyncio.sleep(1.2)
    await hit(redis, "k:exp", limit=1, window_sec=1)


async def test_lockout_flow(redis):
    ip = "1.2.3.4"
    assert not await lockout_active(redis, ip)
    for _ in range(10):
        await mark_failure(redis, ip, threshold=10, lock_window_sec=60)
    assert await lockout_active(redis, ip)
    await reset_failures(redis, ip)
    for _ in range(9):
        await mark_failure(redis, ip, threshold=10, lock_window_sec=60)
