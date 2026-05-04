"""Token estimation and cost bookkeeping helpers for pet calls."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis


def estimate_text_tokens(text: str | None) -> int:
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    chars = len(text)
    englishish = max(1, chars // 4)
    cjkish = int(cjk * 1.1) + max(0, chars - cjk) // 5
    return max(1, englishish, cjkish)


def estimate_turn_tokens(
    *,
    system: str,
    messages: list[dict[str, Any]],
    reply: str | None,
) -> dict[str, int]:
    input_text = system + "\n" + "\n".join(str(m.get("content", "")) for m in messages)
    output = estimate_text_tokens(reply)
    inp = estimate_text_tokens(input_text)
    return {
        "estimated_input_tokens": inp,
        "estimated_output_tokens": output,
        "estimated_total_tokens": inp + output,
    }


def output_budget_for(mode: str, budgets: dict[str, int]) -> int:
    return int(budgets.get(mode) or budgets.get("free_chat") or 100)


def temperature_for_mode(mode: str) -> float:
    if mode in ("selection_explain", "code_assist"):
        return 0.55
    if mode in ("summary_react", "selection_qa", "follow_up", "article_finished"):
        return 0.7
    if mode == "idle_monologue":
        return 0.9
    return 0.8


async def check_mode_daily_limit(
    redis: Redis,
    *,
    visitor_hash: str,
    mode: str,
    limits: dict[str, int],
) -> str | None:
    limit = int(limits.get(mode, 0))
    if limit <= 0:
        return "mode_disabled"
    day = datetime.now(UTC).strftime("%Y%m%d")
    key = f"rl:pet:mode:{day}:{visitor_hash}:{mode}"
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, 60 * 60 * 26)
    if n > limit:
        return "mode_daily_limit"
    return None
