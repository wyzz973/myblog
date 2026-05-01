from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import update

from app.db import engine
from app.models import SiteMeta
from app.services.pet_adapters import anthropic as anthropic_adapter


@pytest.fixture(autouse=True)
async def reset_pet_config(request):
    """Reset pet_config to defaults before each test that hits the HTTP endpoints."""
    if "client" not in request.fixturenames:
        yield
        return
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.pet import PetConfig

    defaults = PetConfig().model_dump()
    async with AsyncSession(engine) as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=defaults))
        await s.commit()
    yield


async def test_ping_with_valid_key():
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=AsyncMock())
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        ok = await anthropic_adapter.ping("sk-test", "claude-haiku-4-5-20251001")
        assert ok is True


async def test_ping_with_bad_key():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("auth")):
        ok = await anthropic_adapter.ping("sk-bad", "claude-haiku-4-5-20251001")
        assert ok is False




async def test_public_pet_config_returns_safe_subset(client):
    r = await client.get("/api/pet/config")
    assert r.status_code == 200
    body = r.json()
    assert "species" in body
    assert "model" not in body
    assert "system_prompt" not in body
    assert "fallback_lines" not in body


async def test_public_pet_summon_returns_quip(client):
    """With no integrations configured, summon returns a fallback line."""
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    body = r.json()
    assert "quip" in body
    assert body["source"] in ("llm", "fallback", "zhipu", "qwen", "doubao", "anthropic")


async def test_public_pet_summon_rate_limit(client, redis):
    for _ in range(6):
        r = await client.post("/api/pet/summon", json={})
        assert r.status_code == 200
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    j = r.json()
    assert j["source"] == "rate_limited"
    assert j["quip"]


async def test_summon_greet_no_post(client):
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    j = r.json()
    assert "quip" in j and "source" in j


async def test_summon_comment_passes_post_title_to_prompt(client, fake_post_id, monkeypatch):
    captured = {}

    async def fake_summon(**kw):
        captured.update(kw)
        return ("hi", "zhipu")

    from app.services import pet_gateway
    monkeypatch.setattr(pet_gateway, "summon", fake_summon)

    r = await client.post("/api/pet/summon", json={"post_id": fake_post_id})
    assert r.status_code == 200
    # The user prompt should mention the article title
    assert "Title:" in captured["user"]


async def test_summon_explain_truncates_selection(client, fake_post_id, monkeypatch):
    captured = {}

    async def fake_summon(**kw):
        captured.update(kw)
        return ("explain ok", "zhipu")

    from app.services import pet_gateway
    monkeypatch.setattr(pet_gateway, "summon", fake_summon)

    long_sel = "x" * 2000
    r = await client.post(
        "/api/pet/summon",
        json={"post_id": fake_post_id, "selection": long_sel},
    )
    assert r.status_code == 200
    # Default max_context_chars is 500
    assert captured["user"].count("x") <= 500


async def test_summon_returns_tired_line_when_rate_limited(client, monkeypatch):
    async def fake_check_pet(*a, **kw):
        return "per_ip_per_min"

    from app.services import rate_limit
    monkeypatch.setattr(rate_limit, "check_pet", fake_check_pet)

    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    j = r.json()
    assert j["source"] == "rate_limited"
    assert j["quip"]  # non-empty
