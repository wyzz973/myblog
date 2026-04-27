from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import Media, SiteMeta

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


async def test_media_delete_removes_row(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    """Insert a Media row pointing at a path that doesn't exist on disk;
    DELETE should remove the row + idempotently no-op on the missing file."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
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
    """site_meta.avatar_id = id; DELETE media → avatar_id becomes NULL via ON DELETE SET NULL."""
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s)
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=mid))
        await s.commit()

    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
        assert site.avatar_id is None
        # Cleanup so the next test sees a clean fixture.
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=None))
        await s.commit()


def _png_bytes(w=4, h=3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 200, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def test_media_post_single_png(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)

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


async def test_media_post_partial_failure(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    """Two valid PNGs + one oversize. ok=2, failed=1, no abort."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)

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
