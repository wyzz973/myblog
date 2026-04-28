from datetime import date, timedelta

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent, Post, Tag

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def clean_analytics():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.execute(delete(HitDaily))
        await s.commit()


async def test_dashboard_unauthenticated_401(client, clean_analytics):
    r = await client.get("/api/admin/dashboard")
    assert r.status_code == 401


async def test_dashboard_empty_returns_zeros(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hits"]["today"] == 0
    assert body["hits"]["last_7d"] == 0
    assert body["hits"]["last_30d"] == 0
    assert "likes" in body and "comments" in body and "posts" in body and "media" in body


async def test_dashboard_today_hits_visible(client, admin_token, clean_analytics):
    from datetime import UTC, datetime
    async with AsyncSessionLocal() as s:
        for _ in range(7):
            s.add(HitEvent(path="/", created_at=datetime.now(UTC)))
        await s.commit()

    r = await client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.json()["hits"]["today"] == 7


async def test_analytics_unauthenticated_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics")
    assert r.status_code == 401


async def test_analytics_default_30_days(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "timeseries" in body
    assert len(body["timeseries"]) == 30
    assert all(p["hits"] == 0 for p in body["timeseries"])


async def test_analytics_days_clamp_lower(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?days=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_analytics_days_clamp_upper(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?days=10000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["timeseries"]) == 365


async def test_analytics_posts_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics/posts")
    assert r.status_code == 401


async def test_analytics_tags_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics/tags")
    assert r.status_code == 401


async def test_analytics_posts_returns_titled_rows(
    client, admin_token, clean_analytics
):
    yesterday = date.today() - timedelta(days=1)
    slug = "p6b-analytics-posttest"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p6btest-admin-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p6btest-admin-tag", name="Admin Tag",
                      color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p6btest-admin-tag")
            )).first()
        s.add(Post(
            id=slug, n="1", title="Post Test", subtitle="", date=date(2026, 4, 28),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=yesterday, path=f"/post/{slug}",
                       hits=21, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/analytics/posts?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        match = next((p for p in body if p["post_id"] == slug), None)
        assert match is not None
        assert match["title"] == "Post Test"
        assert match["hits"] == 21
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.post_id == slug))
            await s.execute(sa_delete(Post).where(Post.id == slug))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-admin-tag"))
            await s.commit()


async def test_analytics_posts_excludes_deleted(
    client, admin_token, clean_analytics
):
    """Deleting the post makes hit_daily.post_id become NULL via FK SET NULL,
    so the post no longer appears in /analytics/posts."""
    from sqlalchemy import delete as sa_delete
    yesterday = date.today() - timedelta(days=1)
    slug = "p6b-fk-test"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p6btest-fk-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p6btest-fk-tag", name="FK Tag",
                      color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p6btest-fk-tag")
            )).first()
        s.add(Post(
            id=slug, n="1", title="Will Delete", subtitle="", date=date(2026, 4, 28),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=yesterday, path=f"/post/{slug}",
                       hits=5, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()

    async with AsyncSessionLocal() as s:
        await s.execute(sa_delete(Post).where(Post.id == slug))
        await s.commit()

    try:
        r = await client.get(
            "/api/admin/analytics/posts?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert all(p["post_id"] != slug for p in body)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.path == f"/post/{slug}"))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-fk-tag"))
            await s.commit()
