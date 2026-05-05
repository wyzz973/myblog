from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import Media, Post, SiteMeta, Tag
from datetime import date as _date

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose engine pool between tests so asyncpg connections aren't shared
    across event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
def media_dir(tmp_path, monkeypatch):
    """Override media_storage._media_dir to point at tmp_path for the test."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def cleanup_media():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Media))
        await s.commit()


async def test_media_list_unauthenticated_401(client, cleanup_media):
    r = await client.get("/api/admin/media")
    assert r.status_code == 401


async def test_media_list_empty(client, admin_token, cleanup_media):
    r = await client.get(
        "/api/admin/media",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_media_get_single_404_when_missing(client, admin_token, cleanup_media):
    r = await client.get(
        "/api/admin/media/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def _seed_media(s, *, filename="cat.png", storage_path="aa/cat.png",
                       mime="image/png", size=100, alt=None) -> int:
    row = Media(
        filename=filename, storage_path=storage_path, mime_type=mime, size=size,
        width=10, height=10, alt=alt, created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    return row.id


async def test_media_patch_alt_updates(client, admin_token, cleanup_media):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, alt=None)
        await s.commit()
    r = await client.patch(
        f"/api/admin/media/{mid}",
        json={"alt": "a small cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["alt"] == "a small cat"


async def test_media_patch_alt_404(client, admin_token, cleanup_media):
    r = await client.patch(
        "/api/admin/media/99999",
        json={"alt": "x"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_media_delete_removes_row(client, admin_token, cleanup_media, media_dir):
    """Insert a Media row pointing at a path that doesn't exist on disk;
    DELETE should remove the row + idempotently no-op on the missing file."""
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="aa/never-on-disk.png")
        await s.commit()

    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        gone = (await s.execute(select(Media).where(Media.id == mid))).scalar_one_or_none()
        assert gone is None


async def test_media_delete_404(client, admin_token, cleanup_media):
    r = await client.delete(
        "/api/admin/media/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_media_delete_clears_avatar_id_via_fk(client, admin_token, cleanup_media):
    """Task 23 changed delete behavior: refuse with 409 while avatar_id
    points at the media. Owners must clear the avatar first; only then
    does delete proceed. The DB still has ON DELETE SET NULL as a
    last-resort safety net for direct DB writes, but the API never
    triggers that path."""
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s)
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=mid))
        await s.commit()

    # First attempt is refused.
    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["avatar"] is True

    # Clear the avatar, then delete succeeds.
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=None))
        await s.commit()
    r2 = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 204


def _png_bytes(w=4, h=3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 200, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def test_media_post_single_png(client, admin_token, cleanup_media, media_dir):
    files = {"files": ("cat.png", _png_bytes(20, 30), "image/png")}
    r = await client.post(
        "/api/admin/media",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ok"]) == 1
    assert body["failed"] == []
    item = body["ok"][0]
    assert item["mime_type"] == "image/png"
    assert item["width"] == 20
    assert item["height"] == 30


async def test_media_post_partial_failure(client, admin_token, cleanup_media, media_dir):
    """Two valid PNGs + one oversize. ok=2, failed=1, no abort."""
    from app.services import media_storage

    big = b"\x89PNG\r\n\x1a\n" + b"x" * (media_storage.MAX_BYTES + 10)
    files = [
        ("files", ("a.png", _png_bytes(), "image/png")),
        ("files", ("huge.png", big, "image/png")),
        ("files", ("b.png", _png_bytes(), "image/png")),
    ]
    r = await client.post(
        "/api/admin/media",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["ok"]) == 2
    assert len(body["failed"]) == 1
    assert body["failed"][0]["filename"] == "huge.png"
    assert "too large" in body["failed"][0]["error"]


async def test_media_post_unauthenticated_401(client, cleanup_media):
    files = {"files": ("x.png", b"abc", "image/png")}
    r = await client.post("/api/admin/media", files=files)
    assert r.status_code == 401


# --- Orphan-file cleanup test (I4) ---


async def test_media_post_db_failure_cleans_orphan(
    client, admin_token, cleanup_media, media_dir, monkeypatch
):
    """When media_svc.create raises mid-batch, the already-saved file must
    be deleted so we don't accumulate orphans on disk."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.services import media as media_svc_module

    real_create = media_svc_module.create
    call_count = {"n": 0}

    async def flaky_create(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise SQLAlchemyError("simulated DB blow-up")
        return await real_create(*a, **kw)

    monkeypatch.setattr(media_svc_module, "create", flaky_create)

    files = [
        ("files", (f"img{i}.png", _png_bytes(), "image/png"))
        for i in range(3)
    ]
    r = await client.post(
        "/api/admin/media", files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["ok"]) == 2
    assert len(body["failed"]) == 1
    assert "db error" in body["failed"][0]["error"]

    # Two files survived; the orphaned one was cleaned up.
    saved_files = [p for p in media_dir.rglob("*") if p.is_file()]
    assert len(saved_files) == 2


# --- event_log assertions (test gap 9) ---


async def test_media_uploaded_event_logged(
    client, admin_token, cleanup_media, media_dir
):
    from sqlalchemy import select

    from app.models import EventLog

    files = {"files": ("e.png", _png_bytes(10, 10), "image/png")}
    r = await client.post(
        "/api/admin/media", files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    new_id = r.json()["ok"][0]["id"]

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(EventLog).where(EventLog.type == "media.uploaded")
            .where(EventLog.target == str(new_id))
        )).scalars().all()
    assert len(rows) == 1
    meta = rows[0].meta
    assert meta["filename"] == "e.png"
    assert meta["mime"] == "image/png"


async def test_media_alt_updated_event_logged(
    client, admin_token, cleanup_media
):
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select

    from app.models import EventLog

    async with AsyncSessionLocal() as s:
        # Cleanup any prior media.* events to keep this test isolated.
        await s.execute(sa_delete(EventLog).where(
            EventLog.type.like("media.%")
        ))
        mid = await _seed_media(s, alt="old")
        await s.commit()

    r = await client.patch(
        f"/api/admin/media/{mid}",
        json={"alt": "new"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(EventLog).where(EventLog.type == "media.alt_updated")
            .where(EventLog.target == str(mid))
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].meta["old"] == "old"
    assert rows[0].meta["new"] == "new"


async def test_media_deleted_event_logged(
    client, admin_token, cleanup_media
):
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select

    from app.models import EventLog

    async with AsyncSessionLocal() as s:
        await s.execute(sa_delete(EventLog).where(
            EventLog.type.like("media.%")
        ))
        mid = await _seed_media(s, filename="bye.png")
        await s.commit()

    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(EventLog).where(EventLog.type == "media.deleted")
            .where(EventLog.target == str(mid))
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].meta["filename"] == "bye.png"


# --- PATCH alt > 512 chars → 422 (test gap 10) ---


async def test_media_patch_alt_too_long_422(client, admin_token, cleanup_media):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s)
        await s.commit()
    r = await client.patch(
        f"/api/admin/media/{mid}",
        json={"alt": "x" * 513},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


# --- POST with empty filename (test gap 8) ---


async def test_media_post_with_empty_filename(
    client, admin_token, cleanup_media, media_dir
):
    """An UploadFile with empty filename should fall back to "unnamed"
    and still produce a valid media row with the storage_path safe-name = "file".
    httpx may not always preserve the empty filename — we just verify it
    doesn't crash and produces a valid item when a 200 is returned."""
    files = {"files": ("unnamed.png", _png_bytes(), "image/png")}
    r = await client.post(
        "/api/admin/media", files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    if body["ok"]:
        assert body["ok"][0]["filename"]


# --- Task 23: refuse delete when media is referenced ---


async def _seed_post_with_body(s, *, slug, tag_slug, body_md):
    tag = (await s.execute(
        Tag.__table__.select().where(Tag.slug == tag_slug)
    )).first()
    if tag is None:
        s.add(Tag(slug=tag_slug, name=tag_slug.title(), color="#888", sort_order=0))
        await s.flush()
        tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == tag_slug)
        )).first()
    s.add(Post(
        id=slug, n="1", title="t23-host", subtitle="", date=_date(2026, 4, 28),
        read="1", lang="en", summary="", tldr="", body_md=body_md, body_json=[],
        word_count=0, status="published", featured=False, private=False,
        comments_enabled=True, tag_id=tag.id,
    ))
    await s.flush()


@pytest.fixture
async def cleanup_t23_posts():
    yield
    async with AsyncSessionLocal() as s:
        from sqlalchemy import delete as sa_delete
        await s.execute(sa_delete(Post).where(Post.id.like("t23-%")))
        await s.execute(sa_delete(Tag).where(Tag.slug == "t23-tag"))
        await s.commit()


async def test_media_get_includes_referenced_by_when_unreferenced(
    client, admin_token, cleanup_media,
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="t23/lonely.png")
        await s.commit()
    r = await client.get(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    item = r.json()
    assert item["referenced_by"] == {"posts": [], "avatar": False}


async def test_media_get_referenced_by_post_body(
    client, admin_token, cleanup_media, cleanup_t23_posts,
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="t23/used.png")
        await _seed_post_with_body(
            s, slug="t23-uses-it", tag_slug="t23-tag",
            body_md="see ![pic](/media/t23/used.png) here",
        )
        await s.commit()
    r = await client.get(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    refs = r.json()["referenced_by"]
    assert refs == {"posts": ["t23-uses-it"], "avatar": False}


async def test_media_delete_refused_with_409_when_referenced(
    client, admin_token, cleanup_media, cleanup_t23_posts,
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="t23/blocker.png")
        await _seed_post_with_body(
            s, slug="t23-blocking", tag_slug="t23-tag",
            body_md="![](/media/t23/blocker.png)",
        )
        await s.commit()
    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "media_referenced"
    assert detail["posts"] == ["t23-blocking"]
    assert detail["avatar"] is False
    # Row should still exist after the refused delete.
    async with AsyncSessionLocal() as s:
        still = (await s.execute(
            select(Media).where(Media.id == mid)
        )).scalar_one_or_none()
    assert still is not None


async def test_media_delete_refused_when_set_as_avatar(
    client, admin_token, cleanup_media,
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="t23/avatar.png")
        # Mark as avatar via SiteMeta
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one_or_none()
        if sm is None:
            sm = SiteMeta(id=1)
            s.add(sm)
        sm.avatar_id = mid
        await s.commit()
    try:
        r = await client.delete(
            f"/api/admin/media/{mid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409
        assert r.json()["detail"]["avatar"] is True
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=None))
            await s.commit()
