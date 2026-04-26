from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import Comment, Post, Tag

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def seed_post():
    pid = "p4-admin-comments"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="905", title="t", tag_id=tag.id, date=date(2026, 1, 1),
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


async def _seed_comments(post_id):
    async with AsyncSessionLocal() as s:
        s.add_all([
            Comment(post_id=post_id, who="a", email_hash="h" * 64,
                    body="pending one", status="pending", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
            Comment(post_id=post_id, who="b", email_hash="h" * 64,
                    body="approved one", status="approved", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
            Comment(post_id=post_id, who="c", email_hash="h" * 64,
                    body="spam one", status="spam", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
        ])
        await s.commit()


async def test_admin_list_all_no_filter(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        "/api/admin/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    statuses = [c["status"] for c in items if c["post_id"] == seed_post]
    assert sorted(statuses) == ["approved", "pending", "spam"]


async def test_admin_list_filter_by_status(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        "/api/admin/comments?status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = [c for c in r.json() if c["post_id"] == seed_post]
    assert len(items) == 1
    assert items[0]["status"] == "pending"


async def test_admin_delete_204(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.delete(
        f"/api/admin/comments/{cid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Comment).where(Comment.id == cid))).scalar_one_or_none()
        assert row is None


async def test_admin_delete_unknown_404(client, admin_token):
    r = await client.delete(
        "/api/admin/comments/99999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
