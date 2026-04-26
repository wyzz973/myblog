from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import Comment, Post, Tag


@pytest.fixture
async def seed_post():
    pid = "p4-comments-pub"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="903", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_post_comment_returns_pending(client, seed_post):
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "alice", "email": "alice@example.com", "body": "Hi there"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)


async def test_post_comment_persists_email_as_hash_only(client, seed_post):
    await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "bob", "email": "bob@example.com", "body": "hello"},
    )
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(select(Comment).where(Comment.post_id == seed_post))
        ).scalars().all()
        assert any("bob@example.com" not in (r.body or "") for r in rows)
        for r in rows:
            assert r.email_hash and len(r.email_hash) == 64
            assert "@" not in r.email_hash


async def test_post_comment_disabled_post_403(client):
    pid = "p4-disabled-comments"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="904", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=False,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        r = await client.post(
            f"/api/posts/{pid}/comments",
            json={"who": "x", "email": "x@y.z", "body": "hi"},
        )
        assert r.status_code == 403
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_post_comment_unknown_post_404(client):
    r = await client.post(
        "/api/posts/never-exists/comments",
        json={"who": "x", "email": "x@y.z", "body": "hi"},
    )
    assert r.status_code == 404


async def test_post_comment_rate_limit(client, seed_post):
    """4th call within 60s → 429."""
    for _ in range(3):
        r = await client.post(
            f"/api/posts/{seed_post}/comments",
            json={"who": "spammer", "email": "s@s.s", "body": "spam"},
        )
        assert r.status_code == 202
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "spammer", "email": "s@s.s", "body": "spam"},
    )
    assert r.status_code == 429


async def test_post_comment_invalid_body(client, seed_post):
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "", "email": "x@y.z", "body": "hi"},
    )
    assert r.status_code == 422
