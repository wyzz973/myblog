"""Anthropic adapter for the pet gateway."""
from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic
import structlog

log = structlog.get_logger(__name__)


async def chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 80,
    temperature: float = 0.9,
    timeout: float = 5.0,  # noqa: ASYNC109 — passed to HTTP client, not asyncio.timeout
) -> str:
    """Single chat call. Raises on failure (caller handles fallback)."""
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text if msg.content else ""
    if not text.strip():
        raise RuntimeError("anthropic returned empty content")
    return text.strip()


async def chat_stream(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 200,
    temperature: float = 0.9,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> AsyncIterator[str]:
    """Yield text deltas from streaming messages.create."""
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text


async def ping(api_key: str, model: str) -> bool:
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=5.0)
        await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("anthropic.ping_failed", model=model, error=repr(e))
        return False
