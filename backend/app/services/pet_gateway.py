"""Pet gateway: tries providers in order, falls back to canned lines."""
from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.services.pet_adapters import anthropic as anthropic_adapter
from app.services.pet_adapters import openai_compat

log = structlog.get_logger(__name__)


PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "zhipu": {
        "adapter": "openai_compat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "adapter": "openai_compat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "doubao": {
        "adapter": "openai_compat",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": None,  # endpoint id required from extra_json
    },
    "anthropic": {
        "adapter": "anthropic",
        "default_model": "claude-haiku-4-5-20251001",
    },
    "deepseek": {
        "adapter": "openai_compat",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-flash",
        "extra_body": {"thinking": {"type": "disabled"}},  # short quips, no reasoning trace
    },
}


async def _call(
    *,
    name: str,
    api_key: str,
    model_override: str | None,
    system: str,
    user: str,
    timeout: float,  # noqa: ASYNC109 — adapter timeout, not asyncio
    max_tokens: int = 80,
    temperature: float = 0.9,
) -> str:
    cfg = PROVIDER_REGISTRY[name]
    model = model_override or cfg["default_model"]
    if model is None:
        raise RuntimeError(f"{name}: no model configured (set extra_json.model)")
    if cfg["adapter"] == "openai_compat":
        return await openai_compat.chat(
            api_key=api_key, base_url=cfg["base_url"], model=model,
            system=system, user=user, timeout=timeout,
            max_tokens=max_tokens, temperature=temperature,
            extra_body=cfg.get("extra_body"),
        )
    if cfg["adapter"] == "anthropic":
        return await anthropic_adapter.chat(
            api_key=api_key, model=model,
            system=system, user=user, timeout=timeout,
            max_tokens=max_tokens, temperature=temperature,
        )
    raise RuntimeError(f"{name}: unknown adapter {cfg['adapter']!r}")


async def summon(
    *,
    providers: list[str],
    secrets: dict[str, dict[str, Any]],  # name -> {key, model}
    system: str,
    user: str,
    fallback_lines: list[str],
    timeout_per_call: float = 5.0,
    max_tokens: int = 80,
    temperature: float = 0.9,
) -> tuple[str, str]:
    """Try each provider in order. Return (text, source).

    `secrets[name]` shape: {"key": str, "model": str | None}.
    Providers without a secret entry are skipped.
    """
    for name in providers:
        if name not in PROVIDER_REGISTRY:
            log.warning("pet_gateway.unknown_provider", name=name)
            continue
        sec = secrets.get(name)
        if not sec or not sec.get("key"):
            log.info("pet_gateway.skip_no_secret", name=name)
            continue
        try:
            text = await _call(
                name=name,
                api_key=sec["key"],
                model_override=sec.get("model"),
                system=system,
                user=user,
                timeout=timeout_per_call,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return text, name
        except Exception as e:  # noqa: BLE001
            log.warning("pet_gateway.provider_failed", name=name, error=repr(e))
            continue
    return random.choice(fallback_lines) if fallback_lines else "...", "fallback"


async def _call_stream(
    *,
    name: str,
    api_key: str,
    model_override: str | None,
    system: str,
    messages: list[dict],
    timeout: float,  # noqa: ASYNC109
    max_tokens: int,
    temperature: float,
) -> AsyncIterator[str]:
    cfg = PROVIDER_REGISTRY[name]
    model = model_override or cfg["default_model"]
    if model is None:
        raise RuntimeError(f"{name}: no model configured (set extra_json.model)")
    if cfg["adapter"] == "openai_compat":
        async for chunk in openai_compat.chat_stream(
            api_key=api_key, base_url=cfg["base_url"], model=model,
            system=system, messages=messages, timeout=timeout,
            max_tokens=max_tokens, temperature=temperature,
            extra_body=cfg.get("extra_body"),
        ):
            yield chunk
        return
    if cfg["adapter"] == "anthropic":
        async for chunk in anthropic_adapter.chat_stream(
            api_key=api_key, model=model,
            system=system, messages=messages, timeout=timeout,
            max_tokens=max_tokens, temperature=temperature,
        ):
            yield chunk
        return
    raise RuntimeError(f"{name}: unknown adapter {cfg['adapter']!r}")


async def summon_stream(
    *,
    providers: list[str],
    secrets: dict[str, dict[str, Any]],
    system: str,
    user: str | None = None,
    messages: list[dict] | None = None,
    fallback_lines: list[str],
    timeout_per_call: float = 30.0,
    max_tokens: int = 200,
    temperature: float = 0.9,
) -> AsyncIterator[dict[str, Any]]:
    """Stream from the first working provider. Yields events:
      - {"type": "chunk", "text": "..."} per delta
      - {"type": "done", "source": "<provider>"} on success
      - {"type": "fallback", "text": "...", "source": "fallback"}
        if all providers fail before producing any chunk

    Pass either `messages` (preferred, full conversation list) or legacy
    `user` (single-turn string). At least one is required.

    If a provider produces partial output then errors mid-stream, we keep
    the partial output (yield 'done') rather than fall back, so the visitor
    isn't shown two different replies.
    """
    if messages is None:
        if user is None:
            raise ValueError("summon_stream requires either `messages` or `user`")
        messages = [{"role": "user", "content": user}]
    for name in providers:
        if name not in PROVIDER_REGISTRY:
            log.warning("pet_gateway.unknown_provider", name=name)
            continue
        sec = secrets.get(name)
        if not sec or not sec.get("key"):
            log.info("pet_gateway.skip_no_secret", name=name)
            continue
        received_any = False
        try:
            async for chunk in _call_stream(
                name=name,
                api_key=sec["key"],
                model_override=sec.get("model"),
                system=system,
                messages=messages,
                timeout=timeout_per_call,
                max_tokens=max_tokens,
                temperature=temperature,
            ):
                received_any = True
                yield {"type": "chunk", "text": chunk}
        except Exception as e:  # noqa: BLE001
            if received_any:
                # Mid-stream failure — keep what we already sent.
                log.warning("pet_gateway.stream_partial_failure", name=name, error=repr(e))
                yield {"type": "done", "source": name}
                return
            log.warning("pet_gateway.stream_provider_failed", name=name, error=repr(e))
            continue
        if received_any:
            yield {"type": "done", "source": name}
            return
        # Provider succeeded but yielded zero chunks — try next.
    fallback = random.choice(fallback_lines) if fallback_lines else "..."
    yield {"type": "fallback", "text": fallback, "source": "fallback"}
