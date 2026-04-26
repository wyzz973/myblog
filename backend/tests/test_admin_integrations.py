from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import Integration

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
async def cleanup_integrations():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Integration))
        await s.commit()


async def test_github_get_empty(client, admin_token, cleanup_integrations):
    r = await client.get(
        "/api/admin/integrations/github",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["username"] is None
    assert "token" not in body


async def test_github_put_invalid_token_422(client, admin_token, cleanup_integrations):
    with patch("app.services.github.ping", new=AsyncMock(return_value=None)):
        r = await client.put(
            "/api/admin/integrations/github",
            json={"username": "alice", "token": "ghp_bad"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 422


async def test_github_put_valid_stores_encrypted_then_syncs(client, admin_token, cleanup_integrations):
    with patch("app.services.github.ping", new=AsyncMock(return_value="alice")), \
         patch("app.services.github.fetch_contributions", new=AsyncMock(return_value=[])):
        r = await client.put(
            "/api/admin/integrations/github",
            json={"username": "alice", "token": "ghp_good"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        row = (await s.execute(select(Integration).where(Integration.name == "github"))).scalar_one()
        assert row.username == "alice"
        assert row.secret_encrypted != "ghp_good"


async def test_anthropic_put_valid(client, admin_token, cleanup_integrations):
    fake_anthropic = AsyncMock()
    fake_anthropic.messages.create.return_value = AsyncMock()
    with patch("app.services.pet_llm.ping", new=AsyncMock(return_value=True)):
        r = await client.put(
            "/api/admin/integrations/anthropic",
            json={"api_key": "sk-ant-xxx", "model": "claude-haiku-4-5-20251001"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200, r.text


async def test_get_never_returns_secret(client, admin_token, cleanup_integrations):
    from app.services import integrations as svc
    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="alice", secret="leaky-secret-xyz")
        await s.commit()
    r = await client.get(
        "/api/admin/integrations/github",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    text = r.text
    assert "leaky-secret-xyz" not in text


async def test_github_manual_sync_endpoint(client, admin_token, cleanup_integrations):
    from app.services import integrations as svc
    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="alice", secret="ghp_token")
        await s.commit()

    with patch("app.services.github.fetch_contributions", new=AsyncMock(return_value=[])):
        r = await client.post(
            "/api/admin/integrations/github/sync",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
