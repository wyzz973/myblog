"""Pet LLM caller using Anthropic SDK + fallback lines."""
from __future__ import annotations

import random

import anthropic
import structlog

log = structlog.get_logger(__name__)


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
    except anthropic.APITimeoutError as e:
        log.warning("pet_llm.ping_timeout", model=model, error=str(e))
    except anthropic.APIStatusError as e:
        log.warning("pet_llm.ping_api_error", model=model, status=e.status_code, error=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("pet_llm.ping_unexpected", model=model, error=repr(e))
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
        log.info("pet_llm.empty_response", model=model)
    except anthropic.APITimeoutError as e:
        log.warning("pet_llm.timeout", model=model, error=str(e))
    except anthropic.APIStatusError as e:
        log.warning("pet_llm.api_error", model=model, status=e.status_code, error=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("pet_llm.unexpected", model=model, error=repr(e))
    return random.choice(fallback_lines) if fallback_lines else "...", "fallback"
