import pytest
import fakeredis.aioredis

from app.services.rate_limit import check_pet


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def test_unlimited_skips_per_minute_layer(redis):
    """Unlimited mode ignores per_ip_per_min even when exceeded."""
    for _ in range(100):
        breach = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=1, per_ip_per_day=1, global_per_day=1,
            unlimited=True, hard_ceiling_per_day=1000,
        )
        assert breach is None


async def test_unlimited_enforces_hard_ceiling(redis):
    """Once daily cumulative > hard_ceiling, it breaches."""
    for _ in range(5):
        b = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True, hard_ceiling_per_day=5,
        )
        assert b is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
        unlimited=True, hard_ceiling_per_day=5,
    )
    assert breach == "hard_ceiling"


async def test_three_layer_still_works_when_unlimited_false(redis):
    """Existing 3-layer behavior unchanged for unlimited=False."""
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach == "per_ip_per_min"
