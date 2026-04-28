"""ARQ analytics_rollup task: rolls hit_events → hit_daily, truncates raw > 30d."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.workers.tasks.analytics import analytics_rollup


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


async def _seed_event(s, *, path, referrer=None, country=None, post_id=None, when):
    s.add(HitEvent(
        path=path, referrer=referrer, country=country, post_id=post_id,
        created_at=when,
    ))


async def test_rollup_aggregates_by_path(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=12)
    async with AsyncSessionLocal() as s:
        for _ in range(5):
            await _seed_event(s, path="/a", when=when)
        for _ in range(3):
            await _seed_event(s, path="/b", when=when)
        await s.commit()

    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["paths_rolled"] == 2

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday)
        )).scalars().all()
    counts = {r.path: r.hits for r in rows}
    assert counts == {"/a": 5, "/b": 3}


async def test_rollup_referrers_and_countries_top(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=2)
    async with AsyncSessionLocal() as s:
        for _ in range(3):
            await _seed_event(s, path="/x", referrer="https://hn.example/", country="US", when=when)
        for _ in range(2):
            await _seed_event(s, path="/x", referrer="https://reddit.example/", country="JP", when=when)
        await _seed_event(s, path="/x", referrer=None, country=None, when=when)
        await s.commit()

    await analytics_rollup({}, target_date=yesterday.isoformat())

    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday).where(HitDaily.path == "/x")
        )).scalar_one()
    assert row.hits == 6
    refs = {item["r"]: item["n"] for item in row.referrers_top}
    assert refs == {"https://hn.example/": 3, "https://reddit.example/": 2}
    countries = {item["c"]: item["n"] for item in row.countries_top}
    assert countries == {"US": 3, "JP": 2}


async def test_rollup_is_idempotent(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=4)
    async with AsyncSessionLocal() as s:
        for _ in range(2):
            await _seed_event(s, path="/y", when=when)
        await s.commit()

    await analytics_rollup({}, target_date=yesterday.isoformat())
    await analytics_rollup({}, target_date=yesterday.isoformat())

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday)
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].hits == 2


async def test_rollup_truncates_raw_older_than_30d(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    old = datetime.now(UTC) - timedelta(days=31)
    recent = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=1)
    async with AsyncSessionLocal() as s:
        await _seed_event(s, path="/old", when=old)
        await _seed_event(s, path="/new", when=recent)
        await s.commit()

    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["rows_truncated"] >= 1

    async with AsyncSessionLocal() as s:
        remaining = (await s.execute(
            select(HitEvent).where(HitEvent.path == "/old")
        )).scalars().all()
    assert remaining == []


async def test_rollup_empty_day(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["paths_rolled"] == 0
