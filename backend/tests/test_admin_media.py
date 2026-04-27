import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import Media

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


from datetime import UTC, datetime


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
