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
