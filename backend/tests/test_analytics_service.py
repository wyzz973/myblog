"""analytics service unit tests (read path)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent, Post, Tag
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


async def test_top_paths_orders_desc(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/big", hits=50,
                       referrers_top=[], countries_top=[]))
        s.add(HitDaily(date=yesterday, path="/small", hits=2,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_paths(s, days=7, limit=5)
    assert [p.path for p in result] == ["/big", "/small"]
    assert result[0].hits == 50


async def test_top_referrers_merges_jsonb(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    two_ago = yesterday - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/a", hits=10,
                       referrers_top=[{"r": "https://hn", "n": 6}, {"r": "https://r", "n": 4}],
                       countries_top=[]))
        s.add(HitDaily(date=two_ago, path="/a", hits=8,
                       referrers_top=[{"r": "https://hn", "n": 5}, {"r": "https://t", "n": 3}],
                       countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_referrers(s, days=7, limit=10)
    by_ref = {p.referrer: p.hits for p in result}
    assert by_ref["https://hn"] == 11
    assert by_ref["https://r"] == 4
    assert by_ref["https://t"] == 3


async def test_top_countries_excludes_null(clean_analytics):
    """countries_top JSON only contains non-NULL countries — confirm
    that NULL country events from today don't appear."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        s.add(HitEvent(path="/", country="US", created_at=now))
        s.add(HitEvent(path="/", country="US", created_at=now))
        s.add(HitEvent(path="/", country=None, created_at=now))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_countries(s, days=7, limit=10)
    assert len(result) == 1
    assert result[0].country == "US"
    assert result[0].hits == 2


async def _seed_post_with_tag(s, *, slug, tag_slug="general", title="Untitled"):
    tag = (await s.execute(
        Tag.__table__.select().where(Tag.slug == tag_slug)
    )).first()
    if tag is None:
        s.add(Tag(slug=tag_slug, name=tag_slug.title(), color="#888", sort_order=0))
        await s.flush()
        tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == tag_slug)
        )).first()
    s.add(Post(
        id=slug, n="1", title=title, subtitle="", date=date(2026, 4, 28),
        read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
        word_count=0, status="published", featured=False, private=False,
        comments_enabled=True, tag_id=tag.id,
    ))
    await s.flush()
    return slug


@pytest.fixture
async def clean_posts_tags():
    yield
    async with AsyncSessionLocal() as s:
        from sqlalchemy import delete as sa_delete
        await s.execute(sa_delete(Post).where(Post.id.like("p6btest-%")))
        await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-tag"))
        await s.commit()


async def test_per_post_groups_by_post_id(clean_analytics, clean_posts_tags):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        slug = await _seed_post_with_tag(
            s, slug="p6btest-howdy", tag_slug="p6btest-tag", title="Howdy"
        )
        s.add(HitDaily(date=yesterday, path="/post/p6btest-howdy",
                       hits=10, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_post(s, days=7)
    titles = {r.post_id: r.title for r in result}
    assert "p6btest-howdy" in titles
    assert titles["p6btest-howdy"] == "Howdy"


async def test_per_post_excludes_null_post_id(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/", hits=99, post_id=None,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_post(s, days=7)
    assert all(r.hits != 99 for r in result)


async def test_per_tag_joins_to_tags(clean_analytics, clean_posts_tags):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        slug = await _seed_post_with_tag(
            s, slug="p6btest-tagjoin", tag_slug="p6btest-tag", title="Tag Join"
        )
        s.add(HitDaily(date=yesterday, path="/post/p6btest-tagjoin",
                       hits=7, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_tag(s, days=7)
    by_slug = {t.slug: t.hits for t in result}
    assert by_slug.get("p6btest-tag", 0) >= 7
