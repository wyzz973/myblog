from unittest.mock import AsyncMock, patch

import pytest

from app.services import pet_gateway

pytestmark = pytest.mark.asyncio


@pytest.fixture
def secrets():
    """Resolves provider name -> api key (with model in extra)."""
    return {
        "zhipu":     {"key": "zk", "model": None},
        "qwen":      {"key": "qk", "model": None},
        "doubao":    {"key": "dk", "model": "ep-xxx"},
        "anthropic": {"key": "ak", "model": None},
    }


async def test_first_provider_succeeds_short_circuits(secrets):
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(return_value="hi")) as oc, \
         patch("app.services.pet_adapters.anthropic.chat", new=AsyncMock(return_value="x")) as an:
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen", "anthropic"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert (text, source) == ("hi", "zhipu")
        assert oc.call_count == 1
        assert an.call_count == 0


async def test_first_fails_second_succeeds(secrets):
    from app.services.pet_adapters.openai_compat import OpenAICompatError
    side = AsyncMock(side_effect=[OpenAICompatError("bad"), "ok"])
    with patch("app.services.pet_adapters.openai_compat.chat", new=side):
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert (text, source) == ("ok", "qwen")
        assert side.call_count == 2


async def test_all_fail_returns_fallback(secrets):
    from app.services.pet_adapters.openai_compat import OpenAICompatError
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(side_effect=OpenAICompatError("x"))), \
         patch("app.services.pet_adapters.anthropic.chat", new=AsyncMock(side_effect=Exception("x"))):
        text, source = await pet_gateway.summon(
            providers=["zhipu", "anthropic"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb1", "fb2"],
        )
        assert text in ("fb1", "fb2")
        assert source == "fallback"


async def test_empty_providers_returns_fallback(secrets):
    text, source = await pet_gateway.summon(
        providers=[],
        secrets=secrets,
        system="s", user="u",
        fallback_lines=["fb"],
    )
    assert text == "fb"
    assert source == "fallback"


async def test_missing_secret_skips_provider(secrets):
    secrets_partial = {"qwen": {"key": "qk", "model": None}}  # zhipu missing
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(return_value="ok")) as oc:
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen"],
            secrets=secrets_partial,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert source == "qwen"
        assert oc.call_count == 1


async def test_doubao_uses_extra_model(secrets):
    captured = {}

    async def mock_chat(*, api_key, base_url, model, **kw):
        captured["model"] = model
        captured["base_url"] = base_url
        return "ok"

    with patch("app.services.pet_adapters.openai_compat.chat", new=mock_chat):
        await pet_gateway.summon(
            providers=["doubao"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert captured["model"] == "ep-xxx"
        assert "ark.cn-beijing.volces.com" in captured["base_url"]


async def test_deepseek_forwards_extra_body(secrets):
    secrets_with_ds = {**secrets, "deepseek": {"key": "dsk", "model": None}}
    captured = {}

    async def mock_chat(*, api_key, base_url, model, system, user, extra_body=None, **kw):
        captured["base_url"] = base_url
        captured["model"] = model
        captured["extra_body"] = extra_body
        return "ok"

    with patch("app.services.pet_adapters.openai_compat.chat", new=mock_chat):
        text, source = await pet_gateway.summon(
            providers=["deepseek"],
            secrets=secrets_with_ds,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert source == "deepseek"
        assert captured["model"] == "deepseek-v4-flash"
        assert "api.deepseek.com" in captured["base_url"]
        assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
