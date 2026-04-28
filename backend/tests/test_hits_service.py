"""hits service unit tests."""
from __future__ import annotations

from datetime import date

import fakeredis.aioredis
import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitEvent, Post
from app.services import hits as hits_svc


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def cleanup_hits():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.commit()


async def _seed_post(s, *, slug="howdy") -> str:
    from app.models import Tag
    tag = (await s.execute(Tag.__table__.select().limit(1))).first()
    if tag is None:
        s.add(Tag(slug="general", name="General", color="#888", sort_order=0))
        await s.flush()
        tag = (await s.execute(Tag.__table__.select().limit(1))).first()
    row = Post(
        id=slug, n="1", title="Howdy", subtitle="", date=date(2026, 4, 28),
        read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
        word_count=0, status="published", featured=False, private=False,
        comments_enabled=True, tag_id=tag.id,
    )
    s.add(row)
    await s.flush()
    return slug


async def test_record_happy_path(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country="US", user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].country == "US"


async def test_record_drops_bot_user_agent(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="GoogleBot/2.1 (compatible)", post_id=None,
        )
        await s.commit()
    assert ok is False
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows == []


async def test_record_dedups_same_ip_path_in_60s(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        ok2 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True
    assert ok2 is False
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1


async def test_record_different_paths_same_ip_both_pass(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        ok2 = await hits_svc.record(
            s, redis=redis, path="/about", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True and ok2 is True


async def test_record_unknown_post_id_falls_back_to_null(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/post/nonexistent", referrer=None,
            ip="1.2.3.4", country=None, user_agent="Mozilla/5.0",
            post_id="nonexistent",
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].post_id is None


async def test_record_known_post_id_persists(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        slug = await _seed_post(s, slug="hits-test-post")
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            ok = await hits_svc.record(
                s, redis=redis, path="/post/hits-test-post", referrer=None,
                ip="1.2.3.4", country=None, user_agent="Mozilla/5.0",
                post_id=slug,
            )
            await s.commit()
        assert ok is True
        async with AsyncSessionLocal() as s:
            rows = (await s.execute(select(HitEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].post_id == slug
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == slug))
            await s.commit()


async def test_record_lowercase_country_becomes_null(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country="us", user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows[0].country is None


@pytest.mark.parametrize("bad", ["USA", "u1", "1A", "", "U"])
async def test_record_non_iso_country_becomes_null(redis, cleanup_hits, bad):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path=f"/?{bad}", referrer=None, ip="1.2.3.4",
            country=bad, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent).where(HitEvent.path == f"/?{bad}"))).scalars().all()
    assert rows[0].country is None


async def test_record_empty_ip_does_not_crash(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/empty-ip", referrer=None, ip="",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True


async def test_record_after_dedup_expiry(redis, cleanup_hits):
    """Manually expire the dedup key to simulate 61s elapsed."""
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="9.9.9.9",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()

    # Drop all dedup keys to simulate TTL expiry.
    async for k in redis.scan_iter("hit:*"):
        await redis.delete(k)

    async with AsyncSessionLocal() as s:
        ok2 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="9.9.9.9",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True and ok2 is True
