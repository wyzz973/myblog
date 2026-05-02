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


async def test_unlimited_uses_default_hard_ceiling_when_kwarg_omitted(redis):
    """Default hard_ceiling_per_day=20000 keeps callers safe if they
    forget to pass it."""
    for _ in range(5):
        breach = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True,
            # hard_ceiling_per_day deliberately omitted → default 20000
        )
        assert breach is None


async def test_unlimited_boundary_at_exact_ceiling_passes(redis):
    """Count == hard_ceiling must NOT breach (uses '>' not '>=')."""
    for i in range(5):
        breach = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True, hard_ceiling_per_day=5,
        )
        assert breach is None, f"breach at request {i + 1} (count={i + 1}, ceiling=5)"
    # 6th call (count=6 > 5) should breach
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
        unlimited=True, hard_ceiling_per_day=5,
    )
    assert breach == "hard_ceiling"


async def test_unlimited_ceiling_counter_shared_across_ips(redis):
    """The hard_ceiling counter is global — different IPs share it.
    Documents the design choice (no per-IP floor in unlimited mode)."""
    for _ in range(3):
        b = await check_pet(
            redis, ip="1.1.1.1",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True, hard_ceiling_per_day=5,
        )
        assert b is None
    # Different IP, same shared ceiling counter
    for _ in range(2):
        b = await check_pet(
            redis, ip="2.2.2.2",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True, hard_ceiling_per_day=5,
        )
        assert b is None
    # 6th request from any IP — total count is now 6, breaches at >5
    b = await check_pet(
        redis, ip="3.3.3.3",
        per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
        unlimited=True, hard_ceiling_per_day=5,
    )
    assert b == "hard_ceiling"
