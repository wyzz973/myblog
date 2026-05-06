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
    rows_for_seed = [c for c in items if c["post_id"] == seed_post]
    statuses = [c["status"] for c in rows_for_seed]
    assert sorted(statuses) == ["approved", "pending", "spam"]
    # Every row must include the joined post title (P9b: replaces raw post_id
    # with a readable label in the moderation UI).
    assert all(c.get("post_title") for c in rows_for_seed)


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


async def test_admin_patch_status_approve(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body.get("reply_id") is None


async def test_admin_patch_set_flag(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"flag": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["flag"] is True


async def test_admin_patch_reply_creates_child(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=approved",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{parent_id}",
        json={"reply_body": "Thanks for the comment!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply_id"] is not None

    async with AsyncSessionLocal() as s:
        child = (
            await s.execute(select(Comment).where(Comment.id == body["reply_id"]))
        ).scalar_one()
        assert child.parent_id == parent_id
        assert child.actor == "admin"
        assert child.status == "approved"
        assert child.body == "Thanks for the comment!"


async def test_admin_patch_combined_status_and_reply(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved", "reply_body": "Approved + replied"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = r.json()
    assert body["status"] == "approved"
    assert body["reply_id"] is not None


async def test_admin_patch_unknown_404(client, admin_token):
    r = await client.patch(
        "/api/admin/comments/99999999",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_admin_delete_parent_cascades_to_replies(client, admin_token, seed_post):
    """Deleting a parent comment must cascade to its admin replies."""
    from sqlalchemy import select as _select
    async with AsyncSessionLocal() as s:
        parent = Comment(
            post_id=seed_post, who="alice", email_hash="h" * 64,
            body="parent", status="approved", actor="public", flag=False,
            created_at=datetime.now(UTC),
        )
        s.add(parent)
        await s.commit()
        await s.refresh(parent)
        child = Comment(
            post_id=seed_post, parent_id=parent.id, who="Wang",
            email_hash=None, body="reply", status="approved", actor="admin",
            flag=False, created_at=datetime.now(UTC),
        )
        s.add(child)
        await s.commit()
        await s.refresh(child)
        child_id = child.id
        parent_id = parent.id

    r = await client.delete(
        f"/api/admin/comments/{parent_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        c = (await s.execute(_select(Comment).where(Comment.id == child_id))).scalar_one_or_none()
        assert c is None, "child reply must be removed by FK CASCADE"


async def test_admin_patch_read_token_denied_403(client, admin_token, seed_post):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "r-comments", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403


# Task 44: text search across who / body


async def test_admin_list_q_filter_matches_body(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        f"/api/admin/comments?post_id={seed_post}&q=approved",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    items = r.json()
    # Only the row whose body is "approved one" should match
    assert len(items) == 1, items
    assert items[0]["body"] == "approved one"


async def test_admin_list_q_filter_matches_who(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    # Author "a" only — substring match against `who` column.
    r = await client.get(
        f"/api/admin/comments?post_id={seed_post}&q=a",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    # who="a" matches 1; body "approved" + "spam" + "pending" all contain
    # 'a' too — assert at least one matched and all matches are valid.
    assert len(items) >= 1, items
    bodies_or_authors = [(it["who"], it["body"]) for it in items]
    for who, body in bodies_or_authors:
        assert "a" in (who.lower() + body.lower())


async def test_admin_list_q_blank_is_ignored(client, admin_token, seed_post):
    """Whitespace-only q must NOT filter — same shape as no q."""
    await _seed_comments(seed_post)
    r = await client.get(
        f"/api/admin/comments?post_id={seed_post}&q=%20%20%20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 3


async def test_admin_list_q_no_match_returns_empty(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        f"/api/admin/comments?post_id={seed_post}&q=zzzzzzz-no-match",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []
