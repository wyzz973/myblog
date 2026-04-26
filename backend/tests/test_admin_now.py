import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import NowEntry

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the engine pool before each test so asyncpg connections are
    not carried across test-local event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def cleanup_now():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(NowEntry))
        await s.commit()


async def test_now_list_empty(client, admin_token, cleanup_now):
    r = await client.get(
        "/api/admin/now",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_now_create_with_current(client, admin_token, cleanup_now):
    r = await client.post(
        "/api/admin/now",
        json={"body_md": "today", "listening": "Boards of Canada", "is_current": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_current"] is True
    assert body["listening"] == "Boards of Canada"


async def test_now_create_flips_prior_current(client, admin_token, cleanup_now):
    a = await client.post(
        "/api/admin/now",
        json={"body_md": "first", "is_current": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    aid = a.json()["id"]
    b = await client.post(
        "/api/admin/now",
        json={"body_md": "second", "is_current": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert b.json()["is_current"] is True

    async with AsyncSessionLocal() as s:
        first = (await s.execute(select(NowEntry).where(NowEntry.id == aid))).scalar_one()
        assert first.is_current is False


async def test_now_patch(client, admin_token, cleanup_now):
    a = await client.post(
        "/api/admin/now",
        json={"body_md": "body", "is_current": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    nid = a.json()["id"]
    r = await client.patch(
        f"/api/admin/now/{nid}",
        json={"reading": "新书"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["reading"] == "新书"


async def test_now_delete(client, admin_token, cleanup_now):
    a = await client.post(
        "/api/admin/now",
        json={"body_md": "del me", "is_current": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    nid = a.json()["id"]
    r = await client.delete(
        f"/api/admin/now/{nid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
