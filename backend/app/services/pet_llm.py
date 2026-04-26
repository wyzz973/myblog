"""Pet LLM caller using Anthropic SDK + fallback lines."""
from __future__ import annotations

import random

import anthropic


async def ping(api_key: str, model: str) -> bool:
    """Return True iff a tiny messages.create succeeds with this key."""
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=5.0)
        await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True
    except Exception:  # noqa: BLE001
        return False


async def summon(
    *,
    api_key: str,
    system_prompt: str,
    model: str,
    fallback_lines: list[str],
) -> tuple[str, str]:
    """Returns (quip, source). source ∈ {'llm', 'fallback'}."""
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=5.0)
        msg = await client.messages.create(
            model=model,
            max_tokens=80,
            temperature=0.9,
            system=system_prompt,
            messages=[{"role": "user", "content": "summon"}],
        )
        text = msg.content[0].text if msg.content else ""
        if text.strip():
            return text.strip(), "llm"
    except Exception:  # noqa: BLE001
        pass
    return random.choice(fallback_lines) if fallback_lines else "...", "fallback"
