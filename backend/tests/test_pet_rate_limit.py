import pytest
from fakeredis.aioredis import FakeRedis

from app.services import rate_limit

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def redis():
    r = FakeRedis()
    yield r
    await r.flushall()
    await r.aclose()


async def test_check_pet_passes_under_limits(redis):
    res = await rate_limit.check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=6, per_ip_per_day=30, global_per_day=500,
    )
    assert res is None  # no breach


async def test_check_pet_per_minute_breach(redis):
    for _ in range(6):
        await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=6, per_ip_per_day=30, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=6, per_ip_per_day=30, global_per_day=500)
    assert res == "per_ip_per_min"


async def test_check_pet_per_day_breach(redis):
    for _ in range(30):
        await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=999, per_ip_per_day=30, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=999, per_ip_per_day=30, global_per_day=500)
    assert res == "per_ip_per_day"


async def test_check_pet_global_breach(redis):
    # Fill global with many IPs
    for i in range(500):
        await rate_limit.check_pet(redis, ip=f"10.0.0.{i % 255}",
                                   per_ip_per_min=999, per_ip_per_day=999, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="9.9.9.9",
                                     per_ip_per_min=999, per_ip_per_day=999, global_per_day=500)
    assert res == "global_per_day"


async def test_check_pet_returns_first_breach_only(redis):
    # Both per_min and per_day would breach — should report per_min (checked first)
    for _ in range(6):
        await rate_limit.check_pet(redis, ip="1.1.1.1", per_ip_per_min=6, per_ip_per_day=10, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.1.1.1", per_ip_per_min=6, per_ip_per_day=10, global_per_day=500)
    assert res == "per_ip_per_min"
