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


async def test_get_comments_only_approved(client, seed_post):
    """Pending comments must not appear in GET response."""
    async with AsyncSessionLocal() as s:
        s.add_all([
            Comment(post_id=seed_post, who="approved", email_hash="h" * 64,
                    body="visible", status="approved", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
            Comment(post_id=seed_post, who="pending", email_hash="h" * 64,
                    body="hidden", status="pending", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
            Comment(post_id=seed_post, who="spam", email_hash="h" * 64,
                    body="spammy", status="spam", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
        ])
        await s.commit()

    r = await client.get(f"/api/posts/{seed_post}/comments")
    assert r.status_code == 200
    body = r.json()
    bodies = [c["body"] for c in body]
    assert "visible" in bodies
    assert "hidden" not in bodies
    assert "spammy" not in bodies


async def test_get_comments_includes_admin_reply_nested(client, seed_post):
    async with AsyncSessionLocal() as s:
        parent = Comment(post_id=seed_post, who="alice", email_hash="h" * 64,
                         body="What about X?", status="approved", actor="public", flag=False,
                         created_at=datetime.now(UTC))
        s.add(parent)
        await s.commit()
        await s.refresh(parent)
        s.add(Comment(post_id=seed_post, parent_id=parent.id, who="Wang Yang",
                      email_hash=None, body="X is the answer.", status="approved",
                      actor="admin", flag=False, created_at=datetime.now(UTC)))
        await s.commit()

    r = await client.get(f"/api/posts/{seed_post}/comments")
    items = r.json()
    parent_item = next(c for c in items if c["body"] == "What about X?")
    assert parent_item["admin_reply"] is not None
    assert parent_item["admin_reply"]["body"] == "X is the answer."
    assert parent_item["admin_reply"]["who"] == "Wang Yang"


async def test_get_comments_response_omits_email_hash(client, seed_post):
    async with AsyncSessionLocal() as s:
        s.add(Comment(post_id=seed_post, who="alice", email_hash="abcd1234" * 8,
                      body="hi", status="approved", actor="public", flag=False,
                      created_at=datetime.now(UTC)))
        await s.commit()
    r = await client.get(f"/api/posts/{seed_post}/comments")
    body = r.json()
    for item in body:
        assert "email_hash" not in item
        assert "email" not in item
