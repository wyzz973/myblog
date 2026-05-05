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
    with patch("app.services.pet_adapters.anthropic.ping", new=AsyncMock(return_value=True)):
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
    # spec §5.1: response includes last_synced_at
    assert "last_synced_at" in body
    assert body["last_synced_at"] is not None


async def test_anthropic_get_never_returns_api_key(client, admin_token, cleanup_integrations):
    """Symmetric to test_get_never_returns_secret but for anthropic."""
    from app.services import integrations as svc
    async with AsyncSessionLocal() as s:
        await svc.upsert(
            s, name="anthropic", username=None, secret="sk-ant-leaky-xyz",
            extra={"model": "claude-haiku-4-5-20251001"},
        )
        await s.commit()
    r = await client.get(
        "/api/admin/integrations/anthropic",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert "sk-ant-leaky-xyz" not in r.text
    body = r.json()
    assert body["model"] == "claude-haiku-4-5-20251001"


async def test_admin_integrations_unauthenticated_returns_401(client, cleanup_integrations):
    """No bearer token → 401 on every admin integrations route."""
    for method, url in [
        ("GET", "/api/admin/integrations/github"),
        ("GET", "/api/admin/integrations/anthropic"),
        ("PUT", "/api/admin/integrations/github"),
        ("PUT", "/api/admin/integrations/anthropic"),
        ("POST", "/api/admin/integrations/github/sync"),
    ]:
        r = await client.request(method, url, json={})
        assert r.status_code == 401, f"{method} {url} → {r.status_code}"


async def test_github_failed_emits_failed_event(client, admin_token, cleanup_integrations):
    """Manual sync failure must emit integration.github.failed (spec §9 acceptance)."""
    from sqlalchemy import select

    from app.models import EventLog
    from app.services import integrations as svc

    async with AsyncSessionLocal() as s:
        await svc.upsert(s, name="github", username="alice", secret="ghp_token")
        await s.execute(delete(EventLog).where(EventLog.type.like("integration.github.%")))
        await s.commit()

    with patch(
        "app.services.github.fetch_contributions",
        new=AsyncMock(side_effect=RuntimeError("network down")),
    ):
        r = await client.post(
            "/api/admin/integrations/github/sync",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 502

    async with AsyncSessionLocal() as s:
        events = (await s.execute(
            select(EventLog).where(EventLog.type.like("integration.github.%"))
            .order_by(EventLog.id)
        )).scalars().all()
        # Worker emits one failed event before raising; router catches and emits another.
        types = [e.type for e in events]
        assert "integration.github.failed" in types


async def test_get_zhipu_empty_returns_empty_envelope(client, admin_token, cleanup_integrations):
    r = await client.get(
        "/api/admin/integrations/zhipu",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is False


async def test_put_zhipu_stores_secret_and_model(client, admin_token, monkeypatch, cleanup_integrations):
    # Mock the smoke test so we don't hit zhipu.com in unit tests
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/zhipu",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "zhipu-key-xyz", "model": "glm-4-flash"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True
    assert j["model"] == "glm-4-flash"


async def test_put_zhipu_rejects_when_smoke_test_fails(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        from app.services.pet_adapters.openai_compat import OpenAICompatError
        raise OpenAICompatError("auth failed")
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/zhipu",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "bad", "model": "glm-4-flash"},
    )
    assert r.status_code == 422


async def test_put_qwen_stores_secret(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/qwen",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "qwen-key-xyz"},  # model omitted → server uses default
    )
    assert r.status_code == 200
    assert r.json()["configured"] is True
    assert r.json()["model"] == "qwen-turbo"


async def test_put_doubao_requires_model_in_payload(client, admin_token, cleanup_integrations):
    # No smoke test mock — should 422 on schema validation before reaching network
    r = await client.put(
        "/api/admin/integrations/doubao",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "doubao-key"},  # missing required `model`
    )
    assert r.status_code == 422


async def test_put_doubao_with_model(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/doubao",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "doubao-key", "model": "ep-20260501-abc"},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "ep-20260501-abc"


async def test_get_qwen_after_put(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)
    await client.put(
        "/api/admin/integrations/qwen",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "qk-x", "model": "qwen-plus"},
    )
    r = await client.get(
        "/api/admin/integrations/qwen",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True and j["model"] == "qwen-plus"


async def test_get_deepseek_empty_returns_empty_envelope(client, admin_token, cleanup_integrations):
    r = await client.get(
        "/api/admin/integrations/deepseek",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is False


async def test_put_deepseek_stores_secret_and_model(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/deepseek",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "sk-deepseek-xyz", "model": "deepseek-v4-flash"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True
    assert j["model"] == "deepseek-v4-flash"


async def test_get_deepseek_after_put(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)
    await client.put(
        "/api/admin/integrations/deepseek",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "sk-deepseek-xyz"},  # model omitted → server uses default
    )
    r = await client.get(
        "/api/admin/integrations/deepseek",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True
    assert j["model"] == "deepseek-v4-flash"


async def test_put_deepseek_rejects_when_smoke_test_fails(client, admin_token, monkeypatch, cleanup_integrations):
    async def fake_chat(**kw):
        from app.services.pet_adapters.openai_compat import OpenAICompatError
        raise OpenAICompatError("auth failed")
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/deepseek",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "bad-key", "model": "deepseek-v4-flash"},
    )
    assert r.status_code == 422


# --- Task 27a: test-without-save endpoint ---


async def test_test_anthropic_returns_ok_when_ping_succeeds(
    client, admin_token, cleanup_integrations,
):
    with patch("app.services.pet_adapters.anthropic.ping", new=AsyncMock(return_value=True)):
        r = await client.post(
            "/api/admin/integrations/anthropic/test",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"api_key": "sk-good"},
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None}
    # Crucially: nothing persisted.
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(Integration.__table__.select())).all()
    assert rows == []


async def test_test_anthropic_returns_err_when_ping_fails(
    client, admin_token, cleanup_integrations,
):
    with patch("app.services.pet_adapters.anthropic.ping", new=AsyncMock(return_value=False)):
        r = await client.post(
            "/api/admin/integrations/anthropic/test",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"api_key": "sk-bad"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error"]


async def test_test_zhipu_runs_smoke_via_openai_compat(
    client, admin_token, monkeypatch, cleanup_integrations,
):
    async def fake_chat(*_args, **_kwargs):
        return "pong"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)
    r = await client.post(
        "/api/admin/integrations/zhipu/test",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "z-key", "model": "glm-4-flash"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None}


async def test_test_unknown_provider_404(
    client, admin_token, cleanup_integrations,
):
    r = await client.post(
        "/api/admin/integrations/notreal/test",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"token": "x"},
    )
    assert r.status_code == 404


async def test_test_anthropic_missing_key_returns_helpful_error(
    client, admin_token, cleanup_integrations,
):
    r = await client.post(
        "/api/admin/integrations/anthropic/test",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "api_key" in body["error"]


async def test_test_requires_auth(client, cleanup_integrations):
    r = await client.post(
        "/api/admin/integrations/anthropic/test",
        json={"api_key": "x"},
    )
    assert r.status_code == 401


# --- Task 24a: GitHub repo listing endpoint ---


async def test_github_repos_404_when_not_configured(
    client, admin_token, cleanup_integrations,
):
    r = await client.get(
        "/api/admin/integrations/github/repos",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_github_repos_returns_items_when_configured(
    client, admin_token, cleanup_integrations,
):
    # Seed a configured github integration
    with patch("app.services.github.ping", new=AsyncMock(return_value="alice")):
        save = await client.put(
            "/api/admin/integrations/github",
            json={"username": "alice", "token": "ghp_abc"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert save.status_code == 200, save.text

    fake_repos = [
        {
            "name": "myblog",
            "description": "personal site",
            "lang": "Python",
            "stars": 42,
            "archived": False,
            "url": "https://github.com/alice/myblog",
        },
        {
            "name": "old-thing",
            "description": "",
            "lang": "",
            "stars": 0,
            "archived": True,
            "url": "https://github.com/alice/old-thing",
        },
    ]
    with patch("app.services.github.fetch_repos", new=AsyncMock(return_value=fake_repos)):
        r = await client.get(
            "/api/admin/integrations/github/repos",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "alice"
    assert len(body["items"]) == 2
    assert body["items"][0]["name"] == "myblog"
    assert body["items"][0]["stars"] == 42
    assert body["items"][1]["archived"] is True


async def test_github_repos_requires_auth(client, cleanup_integrations):
    r = await client.get("/api/admin/integrations/github/repos")
    assert r.status_code == 401


async def test_github_fetch_repos_caches_per_login(client, cleanup_integrations):
    """Direct service-level test: identical calls hit the live API once.
    Resets the module-local cache before each invocation."""
    from app.services import github as github_svc
    github_svc._repos_cache_clear()

    fake = [{"name": "r1", "description": "", "lang": "", "stars": 0, "archived": False, "url": ""}]

    call_count = 0
    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        class FakeResp:
            status_code = 200
            def json(self):
                return {"data": {"user": {"repositories": {"nodes": [
                    {"name": "r1", "description": None, "isArchived": False,
                     "isFork": False, "stargazerCount": 0, "url": "",
                     "primaryLanguage": None}
                ]}}}}
            text = ""
        return FakeResp()

    with patch("httpx.AsyncClient.post", new=fake_post):
        a = await github_svc.fetch_repos("tok", "alice", limit=10)
        b = await github_svc.fetch_repos("tok", "alice", limit=10)
    assert a == b
    assert call_count == 1, "second call should hit cache"
    assert a[0]["name"] == "r1"
    github_svc._repos_cache_clear()
