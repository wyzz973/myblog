from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import NowEntry


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_now():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(NowEntry))
        await s.commit()


async def test_public_now_empty(client, cleanup_now):
    r = await client.get("/api/now")
    assert r.status_code == 200
    body = r.json()
    assert body["current"] is None
    assert body["history"] == []


async def test_public_now_with_current_and_history(client, cleanup_now):
    async with AsyncSessionLocal() as s:
        s.add_all([
            NowEntry(body_md="now", is_current=True, created_at=datetime.now(UTC)),
            NowEntry(body_md="old1", is_current=False, created_at=datetime.now(UTC) - timedelta(days=1)),
            NowEntry(body_md="old2", is_current=False, created_at=datetime.now(UTC) - timedelta(days=2)),
        ])
        await s.commit()

    r = await client.get("/api/now")
    body = r.json()
    assert body["current"]["body_md"] == "now"
    assert len(body["history"]) == 2
    assert body["history"][0]["body_md"] == "old1"  # newest first


async def test_public_now_history_capped_at_10(client, cleanup_now):
    async with AsyncSessionLocal() as s:
        for i in range(15):
            s.add(NowEntry(
                body_md=f"e{i}", is_current=False,
                created_at=datetime.now(UTC) - timedelta(hours=i),
            ))
        await s.commit()

    r = await client.get("/api/now")
    assert len(r.json()["history"]) == 10
