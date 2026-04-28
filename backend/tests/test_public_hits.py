import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitEvent


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_hits():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.commit()


async def test_post_hit_204(client, cleanup_hits):
    r = await client.post("/api/hit", json={"path": "/foo"})
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].path == "/foo"


async def test_post_hit_missing_path_422(client, cleanup_hits):
    r = await client.post("/api/hit", json={})
    assert r.status_code == 422


async def test_post_hit_dedup_returns_204_but_no_row(client, cleanup_hits):
    r1 = await client.post("/api/hit", json={"path": "/foo"})
    r2 = await client.post("/api/hit", json={"path": "/foo"})
    assert r1.status_code == 204 and r2.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1


async def test_post_hit_unknown_post_id(client, cleanup_hits):
    r = await client.post("/api/hit", json={"path": "/post/x", "post_id": "x"})
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].post_id is None


async def test_post_hit_bot_user_agent(client, cleanup_hits):
    r = await client.post(
        "/api/hit",
        json={"path": "/foo"},
        headers={"User-Agent": "GoogleBot/2.1"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows == []


async def test_post_hit_cf_ipcountry_header(client, cleanup_hits):
    r = await client.post(
        "/api/hit",
        json={"path": "/foo"},
        headers={"CF-IPCountry": "JP"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows[0].country == "JP"
