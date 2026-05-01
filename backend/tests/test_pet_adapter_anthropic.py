from unittest.mock import AsyncMock, patch

import pytest

from app.services.pet_adapters import anthropic as adapter

pytestmark = pytest.mark.asyncio


async def test_chat_returns_text_on_success():
    fake_msg = AsyncMock()
    fake_msg.content = [AsyncMock(text="hi human")]
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=fake_msg)
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        text = await adapter.chat(
            api_key="sk-test",
            model="claude-haiku-4-5-20251001",
            system="be brief",
            user="hello",
            max_tokens=80,
            temperature=0.9,
            timeout=5.0,
        )
        assert text == "hi human"


async def test_chat_raises_on_failure():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("api down")):
        with pytest.raises(Exception, match="api down"):
            await adapter.chat(
                api_key="sk-test",
                model="claude-haiku-4-5-20251001",
                system="x", user="y",
            )


async def test_ping_with_valid_key():
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=AsyncMock())
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        assert await adapter.ping("sk-test", "claude-haiku-4-5-20251001") is True


async def test_ping_with_bad_key():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("auth")):
        assert await adapter.ping("sk-bad", "claude-haiku-4-5-20251001") is False
