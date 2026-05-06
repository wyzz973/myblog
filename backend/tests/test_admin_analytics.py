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


# Task 25b-arbitrary-end


async def test_analytics_from_to_returns_arbitrary_window(
    client, admin_token, clean_analytics
):
    r = await client.get(
        "/api/admin/analytics?from=2026-04-01&to=2026-04-07",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["timeseries"]) == 7
    # Window endpoints are inclusive; first/last dates match the params.
    assert body["timeseries"][0]["date"] == "2026-04-01"
    assert body["timeseries"][-1]["date"] == "2026-04-07"


async def test_analytics_from_to_partial_422(client, admin_token, clean_analytics):
    """`from` without `to` (or vice versa) should reject — both are required."""
    r1 = await client.get(
        "/api/admin/analytics?from=2026-04-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 422, r1.text
    r2 = await client.get(
        "/api/admin/analytics?to=2026-04-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 422, r2.text


async def test_analytics_from_to_inverted_422(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?from=2026-04-30&to=2026-04-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_analytics_from_to_overlong_422(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?from=2024-01-01&to=2026-01-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_analytics_posts_accepts_from_to(
    client, admin_token, clean_analytics
):
    """Companion list /analytics/posts honors arbitrary from/to (Task 25b-companion)."""
    r = await client.get(
        "/api/admin/analytics/posts?from=2026-04-01&to=2026-04-07",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    # Empty result is fine — we just want the endpoint to accept the params.
    assert isinstance(r.json(), list)


async def test_analytics_posts_from_to_partial_422(client, admin_token):
    r = await client.get(
        "/api/admin/analytics/posts?from=2026-04-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_analytics_tags_accepts_from_to(
    client, admin_token, clean_analytics
):
    r = await client.get(
        "/api/admin/analytics/tags?from=2026-04-01&to=2026-04-07",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


async def test_analytics_bundle_companion_lists_use_window(
    client, admin_token, clean_analytics
):
    """Seed two HitDaily rows on different historical dates; assert top_paths
    in the requested window includes only the in-range row."""
    in_date = date(2026, 4, 5)
    out_date = date(2026, 4, 25)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(
            date=in_date, path="/p25b-companion-IN",
            hits=42, post_id=None,
            referrers_top=[], countries_top=[],
        ))
        s.add(HitDaily(
            date=out_date, path="/p25b-companion-OUT",
            hits=99, post_id=None,
            referrers_top=[], countries_top=[],
        ))
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/analytics?from=2026-04-01&to=2026-04-10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        paths = {p["path"]: p["hits"] for p in r.json()["top_paths"]}
        assert paths.get("/p25b-companion-IN") == 42
        assert "/p25b-companion-OUT" not in paths
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(
                sa_delete(HitDaily).where(
                    HitDaily.path.in_(["/p25b-companion-IN", "/p25b-companion-OUT"])
                )
            )
            await s.commit()


async def test_analytics_from_to_seeded_history_visible(
    client, admin_token, clean_analytics
):
    """Seed a HitDaily row inside an arbitrary historical window and assert
    the returned timeseries surfaces it on the right day."""
    seed_day = date(2026, 4, 15)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(
            date=seed_day, path="/p25b-window",
            hits=11, post_id=None,
            referrers_top=[], countries_top=[],
        ))
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/analytics?from=2026-04-10&to=2026-04-20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        ts = r.json()["timeseries"]
        seed_pt = next(p for p in ts if p["date"] == "2026-04-15")
        assert seed_pt["hits"] >= 11, seed_pt
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(
                sa_delete(HitDaily).where(HitDaily.path == "/p25b-window")
            )
            await s.commit()


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


async def test_post_timeseries_404_for_unknown_id(client, admin_token):
    r = await client.get(
        "/api/admin/analytics/posts/p25c-missing/timeseries",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_post_timeseries_unauthenticated_401(client):
    r = await client.get("/api/admin/analytics/posts/anything/timeseries")
    assert r.status_code == 401


async def test_post_timeseries_returns_daily_breakdown(
    client, admin_token, clean_analytics
):
    """Two seeded daily rows for one post → endpoint returns those days as
    non-zero entries inside the requested window, all other days as 0,
    and total = sum."""
    from datetime import datetime as _dt, timezone as _tz
    today = _dt.now(_tz.utc).date()
    d1 = today - timedelta(days=1)
    d3 = today - timedelta(days=3)
    slug = "p25c-timeseries"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p25c-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p25c-tag", name="25c Tag", color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p25c-tag")
            )).first()
        s.add(Post(
            id=slug, n="1", title="25c Post", subtitle="", date=date(2026, 5, 1),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=d1, path=f"/post/{slug}",
                       hits=7, post_id=slug,
                       referrers_top=[], countries_top=[]))
        s.add(HitDaily(date=d3, path=f"/post/{slug}",
                       hits=3, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    try:
        r = await client.get(
            f"/api/admin/analytics/posts/{slug}/timeseries?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["post_id"] == slug
        assert body["title"] == "25c Post"
        assert body["total"] == 10  # 7 + 3
        assert len(body["timeseries"]) == 7
        # Map date → hits and assert d1=7, d3=3, rest=0 (today depends on
        # whether any HitEvent fired for this post during the test, which
        # we don't generate, so today should be 0).
        by_date = {pt["date"]: pt["hits"] for pt in body["timeseries"]}
        assert by_date[d1.isoformat()] == 7
        assert by_date[d3.isoformat()] == 3
        # Everything else (excluding the seeded dates) is 0.
        for iso, hits in by_date.items():
            if iso not in (d1.isoformat(), d3.isoformat()):
                assert hits == 0, f"unexpected hits on {iso}: {hits}"
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.post_id == slug))
            await s.execute(sa_delete(Post).where(Post.id == slug))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p25c-tag"))
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


# --- Task 25a: CSV export of per-post hits ---


async def test_analytics_posts_csv_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics/posts.csv")
    assert r.status_code == 401


async def test_analytics_posts_csv_empty_returns_header_only(
    client, admin_token, clean_analytics
):
    r = await client.get(
        "/api/admin/analytics/posts.csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="analytics-posts-' in r.headers.get("content-disposition", "")
    text = r.content.decode("utf-8-sig").replace("\r\n", "\n")
    assert text.strip() == "post_id,title,hits"


async def test_analytics_posts_csv_includes_seeded_row(
    client, admin_token, clean_analytics
):
    # The service uses UTC dates; using local `date.today()` for yesterday
    # is racy when the test runs in a tz that's ahead of UTC.
    from datetime import UTC, datetime as _dt
    yesterday = _dt.now(UTC).date() - timedelta(days=1)
    slug = "p25a-csv-test"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p25a-csv-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p25a-csv-tag", name="CSV Tag",
                      color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p25a-csv-tag")
            )).first()
        s.add(Post(
            id=slug, n="1", title='Hello, "world"', subtitle="",
            date=date(2026, 4, 28), read="1", lang="en", summary="",
            tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=yesterday, path=f"/post/{slug}",
                       hits=42, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/analytics/posts.csv?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        text = r.content.decode("utf-8-sig").replace("\r\n", "\n")
        lines = text.strip().split("\n")
        assert lines[0] == "post_id,title,hits"
        # Title contains a comma + quotes → CSV must quote-and-escape
        row = next((line for line in lines if line.startswith(slug + ",")), None)
        assert row is not None, f"slug not in csv:\n{text}"
        # csv.writer escapes " as "" and wraps the field in quotes
        assert '"Hello, ""world"""' in row
        assert row.endswith(",42")
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.post_id == slug))
            await s.execute(sa_delete(Post).where(Post.id == slug))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p25a-csv-tag"))
            await s.commit()
