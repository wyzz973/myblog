from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import update

from app.db import engine
from app.models import SiteMeta
from app.services import pet_llm


@pytest.fixture(autouse=True)
async def reset_pet_config(request):
    """Reset pet_config to defaults before each test that hits the HTTP endpoints."""
    if "client" not in request.fixturenames:
        yield
        return
    from app.schemas.pet import PetConfig
    from sqlalchemy.ext.asyncio import AsyncSession

    defaults = PetConfig().model_dump()
    async with AsyncSession(engine) as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=defaults))
        await s.commit()
    yield


async def test_ping_with_valid_key():
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=AsyncMock())
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        ok = await pet_llm.ping("sk-test", "claude-haiku-4-5-20251001")
        assert ok is True


async def test_ping_with_bad_key():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("auth")):
        ok = await pet_llm.ping("sk-bad", "claude-haiku-4-5-20251001")
        assert ok is False


async def test_summon_returns_llm_quip_on_success():
    fake_msg = AsyncMock()
    fake_msg.content = [AsyncMock(text="compiling thoughts...")]
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=fake_msg)
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        quip, source = await pet_llm.summon(
            api_key="sk-test",
            system_prompt="be brief",
            model="claude-haiku-4-5-20251001",
            fallback_lines=["fb1", "fb2"],
        )
        assert quip == "compiling thoughts..."
        assert source == "llm"


async def test_summon_returns_fallback_on_error():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("api down")):
        quip, source = await pet_llm.summon(
            api_key="sk-test",
            system_prompt="x",
            model="claude-haiku-4-5-20251001",
            fallback_lines=["only fb"],
        )
        assert quip == "only fb"
        assert source == "fallback"


async def test_public_pet_config_returns_safe_subset(client):
    r = await client.get("/api/pet/config")
    assert r.status_code == 200
    body = r.json()
    assert "species" in body
    assert "model" not in body
    assert "system_prompt" not in body
    assert "fallback_lines" not in body


async def test_public_pet_summon_returns_quip(client):
    """With no anthropic integration, summon returns a fallback line."""
    r = await client.post("/api/pet/summon")
    assert r.status_code == 200
    body = r.json()
    assert "quip" in body
    assert body["source"] in ("llm", "fallback")


async def test_public_pet_summon_rate_limit(client, redis):
    for _ in range(6):
        r = await client.post("/api/pet/summon")
        assert r.status_code == 200
    r = await client.post("/api/pet/summon")
    assert r.status_code == 429
