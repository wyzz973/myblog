import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent

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
