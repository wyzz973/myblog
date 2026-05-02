"""Generic OpenAI-compatible chat adapter (zhipu, qwen, doubao, ...)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
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


async def chat_stream(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str | None = None,
    messages: list[dict] | None = None,
    max_tokens: int = 200,
    temperature: float = 0.9,
    extra_body: dict[str, Any] | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109 — streaming connections live longer
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[str]:
    """Yield text chunks from a streaming chat/completions call.

    Pass either `messages` (preferred, full conversation list of {role, content})
    or legacy `user` (single-turn string). At least one is required.

    Errors before the first chunk raise OpenAICompatError. Errors mid-stream
    are logged but the partial output is honored (caller decides whether to
    retain or replace).
    """
    if messages is None:
        if user is None:
            raise ValueError("chat_stream requires either `messages` or `user`")
        messages = [{"role": "user", "content": user}]
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            *messages,
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if extra_body:
        body.update(extra_body)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=body) as r:
                if r.status_code >= 400:
                    text = await r.aread()
                    log.warning(
                        "openai_compat.stream_http_error",
                        url=url, status=r.status_code, body=text[:200],
                    )
                    raise OpenAICompatError(f"http {r.status_code}: {text[:200]!r}")
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        data = json.loads(payload)
                        delta = data["choices"][0].get("delta", {})
                        chunk = delta.get("content")
                    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
                        continue
                    if chunk:
                        yield chunk
        except httpx.HTTPError as e:
            log.warning("openai_compat.stream_transport_error", url=url, error=repr(e))
            raise OpenAICompatError(f"transport: {e}") from e
