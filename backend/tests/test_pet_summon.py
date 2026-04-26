from unittest.mock import AsyncMock, patch

import pytest

from app.services import pet_llm


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
