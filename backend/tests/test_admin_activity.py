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
