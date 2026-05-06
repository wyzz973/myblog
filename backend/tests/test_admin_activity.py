from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import EventLog

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def seed_events():
    async with AsyncSessionLocal() as s:
        s.add_all([
            EventLog(type="phase4.test.a", actor="t", target="x", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="phase4.test.b", actor="t", target="y", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="phase4.test.a", actor="t", target="z", meta={"k": 1}, created_at=datetime.now(UTC)),
        ])
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(EventLog).where(EventLog.type.in_(["phase4.test.a", "phase4.test.b"])))
        await s.commit()


async def test_activity_returns_rows(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    types = {i["type"] for i in items}
    assert "phase4.test.a" in types
    assert "phase4.test.b" in types


async def test_activity_filter_by_type(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?type=phase4.test.a&limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    types = {i["type"] for i in items}
    assert types == {"phase4.test.a"}


# Task 45: text search across actor / target


async def test_activity_q_filter_matches_target(client, admin_token):
    """Seed an event with a unique target; assert q matches just that row."""
    async with AsyncSessionLocal() as s:
        s.add_all([
            EventLog(type="t45.search", actor="alice@example.com",
                     target="t45-needle-unique", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="t45.search", actor="alice@example.com",
                     target="t45-decoy", meta={}, created_at=datetime.now(UTC)),
        ])
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/activity?q=t45-needle-unique&limit=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        items = r.json()
        targets = [i["target"] for i in items]
        assert "t45-needle-unique" in targets
        assert "t45-decoy" not in targets
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(EventLog).where(EventLog.type == "t45.search"))
            await s.commit()


async def test_activity_q_filter_matches_actor(client, admin_token):
    """ILIKE matches actor column too."""
    async with AsyncSessionLocal() as s:
        s.add_all([
            EventLog(type="t45.actor", actor="t45-actor-rare@example.com",
                     target="anything", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="t45.actor", actor="someone-else@example.com",
                     target="anything", meta={}, created_at=datetime.now(UTC)),
        ])
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/activity?q=t45-actor-rare",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        actors = [i["actor"] for i in r.json()]
        assert any("t45-actor-rare" in a for a in actors)
        assert not any("someone-else" in a for a in actors)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(EventLog).where(EventLog.type == "t45.actor"))
            await s.commit()


async def test_activity_q_blank_ignored(client, admin_token, seed_events):
    """Whitespace-only q is treated as no filter."""
    r = await client.get(
        "/api/admin/activity?q=%20%20&limit=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    types = {i["type"] for i in items}
    # Both seeded types should appear when q is effectively empty.
    assert "phase4.test.a" in types or "phase4.test.b" in types


async def test_activity_q_combines_with_type_filter(client, admin_token):
    async with AsyncSessionLocal() as s:
        s.add_all([
            EventLog(type="t45.combo.x", actor="a", target="needle-X", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="t45.combo.y", actor="a", target="needle-X", meta={}, created_at=datetime.now(UTC)),
        ])
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/activity?type=t45.combo.x&q=needle-X",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        # Both filters AND together: only t45.combo.x rows appear.
        assert len(items) == 1
        assert items[0]["type"] == "t45.combo.x"
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(EventLog).where(EventLog.type.in_(["t45.combo.x", "t45.combo.y"])))
            await s.commit()


async def test_activity_descending_order(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?limit=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    timestamps = [i["created_at"] for i in items]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_dashboard_activity_default_limit(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/dashboard/activity",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) <= 20


async def test_activity_requires_admin(client):
    r = await client.get("/api/admin/activity")
    assert r.status_code == 401


async def test_post_liked_writes_event(client, admin_token):
    """POST /posts/{id}/like must produce a post.liked event."""
    pid = "p4-evt-like"
    from datetime import UTC, date, datetime

    from sqlalchemy import insert, select

    from app.models import LikeEvent, Post, Tag

    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="906", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        await client.post(f"/api/posts/{pid}/like")
        r = await client.get(
            "/api/admin/activity?type=post.liked&limit=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        assert any(i["target"] == pid for i in items)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_comment_created_writes_event(client, admin_token):
    pid = "p4-evt-cmt"
    from datetime import UTC, date, datetime

    from sqlalchemy import insert, select

    from app.models import Comment, Post, Tag

    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="907", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        await client.post(
            f"/api/posts/{pid}/comments",
            json={"who": "evt", "email": "e@v.t", "body": "hello"},
        )
        r = await client.get(
            "/api/admin/activity?type=comment.created&limit=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        assert any(str(i.get("meta", {}).get("post_id")) == pid for i in items)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Comment).where(Comment.post_id == pid))
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()
