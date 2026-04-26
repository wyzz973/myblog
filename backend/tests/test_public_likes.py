from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert

from app.db import AsyncSessionLocal
from app.models import LikeEvent, Post, Tag


@pytest.fixture
async def seed_post():
    pid = "p4-public-likes"
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="901", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json=[],
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


async def test_first_like_returns_was_new_true(client, seed_post):
    r = await client.post(f"/api/posts/{seed_post}/like")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["likes"] == 1
    assert body["was_new"] is True


async def test_second_like_same_client_idempotent(client, seed_post):
    await client.post(f"/api/posts/{seed_post}/like")
    r = await client.post(f"/api/posts/{seed_post}/like")
    body = r.json()
    assert body["likes"] == 1
    assert body["was_new"] is False


async def test_like_unknown_post_404(client):
    r = await client.post("/api/posts/does-not-exist/like")
    assert r.status_code == 404


async def test_like_private_post_404(client):
    """Private posts are invisible to public — like must also 404, not 200."""
    pid = "p4-private"
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="902", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=True, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        r = await client.post(f"/api/posts/{pid}/like")
        assert r.status_code == 404
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_like_rate_limit(client, seed_post, redis):
    """11th call within 60s → 429."""
    for _ in range(10):
        r = await client.post(f"/api/posts/{seed_post}/like")
        assert r.status_code == 200
    r = await client.post(f"/api/posts/{seed_post}/like")
    assert r.status_code == 429
    assert "Retry-After" in r.headers


async def test_post_detail_shows_actual_likes_count(client, seed_post):
    """After 1 like, GET /posts/{id} must show likes=1, not the hardcoded 0."""
    await client.post(f"/api/posts/{seed_post}/like")
    r = await client.get(f"/api/posts/{seed_post}")
    assert r.status_code == 200
    assert r.json()["likes"] == 1
