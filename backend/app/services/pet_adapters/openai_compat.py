"""Generic OpenAI-compatible chat adapter (zhipu, qwen, doubao, ...)."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class OpenAICompatError(RuntimeError):
    """Raised when an OpenAI-compatible provider call fails or returns empty."""


async def chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 80,
    temperature: float = 0.9,
    extra_body: dict[str, Any] | None = None,
    timeout: float = 5.0,  # noqa: ASYNC109 — httpx client timeout, not asyncio
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Call POST {base_url}/chat/completions and return the first choice's text.

    `extra_body` keys are merged into the request body after the standard fields,
    allowing callers to inject provider-specific parameters (e.g. thinking mode).
    `transport` parameter is for tests (httpx.MockTransport).
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if extra_body:
        body.update(extra_body)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        try:
            r = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as e:
            log.warning("openai_compat.transport_error", url=url, error=repr(e))
            raise OpenAICompatError(f"transport: {e}") from e
        if r.status_code >= 400:
            log.warning("openai_compat.http_error", url=url, status=r.status_code, body=r.text[:200])
            raise OpenAICompatError(f"http {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise OpenAICompatError(f"bad response: {e}") from e
        if not isinstance(text, str) or not text.strip():
            raise OpenAICompatError("empty content")
        return text.strip()
