"""analytics service unit tests (read path)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.services import analytics


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def clean_analytics():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.execute(delete(HitDaily))
        await s.commit()


async def test_timeseries_pads_zero_days(clean_analytics):
    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=7)
    assert len(result) == 7
    assert all(p.hits == 0 for p in result)


async def test_timeseries_today_from_hit_events(clean_analytics):
    """today's hits live in hit_events, not hit_daily — pre-rollup."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        for _ in range(4):
            s.add(HitEvent(path="/a", created_at=now))
        await s.commit()

    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=3)
    today_point = result[-1]
    assert today_point.hits == 4


async def test_timeseries_history_from_hit_daily(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/x", hits=12, post_id=None,
                       referrers_top=[], countries_top=[]))
        s.add(HitDaily(date=yesterday, path="/y", hits=8, post_id=None,
                       referrers_top=[], countries_top=[]))
        await s.commit()

    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=3)
    yesterday_point = next(p for p in result if p.date == yesterday)
    assert yesterday_point.hits == 20


async def test_dashboard_kpis_empty(clean_analytics):
    async with AsyncSessionLocal() as s:
        kpi = await analytics.dashboard_kpis(s)
    assert kpi.hits.today == 0
    assert kpi.hits.last_7d == 0
    assert kpi.hits.last_30d == 0


async def test_dashboard_kpis_today_count(clean_analytics):
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        for _ in range(3):
            s.add(HitEvent(path="/", created_at=now))
        await s.commit()
    async with AsyncSessionLocal() as s:
        kpi = await analytics.dashboard_kpis(s)
    assert kpi.hits.today == 3
    assert kpi.hits.last_7d == 3
    assert kpi.hits.last_30d == 3
