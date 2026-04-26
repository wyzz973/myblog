"""Unit tests for the likes service. Use the real test DB via AsyncSessionLocal."""
import asyncio
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert

from app.db import AsyncSessionLocal
from app.models import LikeEvent, Post, Tag
from app.services.likes import get_count, record_like


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the engine pool before each test so asyncpg connections are
    not carried across test-local event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seed_post():
    """Insert a throwaway post for likes to attach to."""
    pid = "p4-likes-test"
    async with AsyncSessionLocal() as s:
        # ensure a tag exists
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one_or_none()
        assert tag is not None, "seed bootstrap must run before tests"

        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="900", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_record_like_first_call_inserts(seed_post):
    async with AsyncSessionLocal() as s:
        total, was_new = await record_like(s, post_id=seed_post, ip="1.2.3.4")
        assert was_new is True
        assert total == 1


async def test_record_like_same_ip_same_day_idempotent(seed_post):
    async with AsyncSessionLocal() as s:
        await record_like(s, post_id=seed_post, ip="1.2.3.4")
        total, was_new = await record_like(s, post_id=seed_post, ip="1.2.3.4")
        assert was_new is False
        assert total == 1


async def test_record_like_different_ips_accumulate(seed_post):
    async with AsyncSessionLocal() as s:
        await record_like(s, post_id=seed_post, ip="1.2.3.4")
        await record_like(s, post_id=seed_post, ip="5.6.7.8")
        total, _ = await record_like(s, post_id=seed_post, ip="9.10.11.12")
        assert total == 3


async def test_record_like_concurrent_same_ip(seed_post):
    """100 concurrent record_like calls with same (post, ip, day) → exactly 1 row."""
    async def one():
        async with AsyncSessionLocal() as s:
            return await record_like(s, post_id=seed_post, ip="1.2.3.4")

    results = await asyncio.gather(*[one() for _ in range(100)], return_exceptions=False)
    new_count = sum(1 for _, was_new in results if was_new)
    assert new_count == 1
    async with AsyncSessionLocal() as s:
        assert await get_count(s, post_id=seed_post) == 1


async def test_get_count_zero_for_unliked():
    async with AsyncSessionLocal() as s:
        assert await get_count(s, post_id="never-liked") == 0
