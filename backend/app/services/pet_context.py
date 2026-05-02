"""Per-visitor short-term conversation context for the pet.

Keyed by visitor_hash (ip_hash[:16]); stored as a Redis list with a
2h sliding TTL and capped at 2*max_turns members. Newest first
(LPUSH); load() reverses to chronological order.

Failures during load/append are NOT propagated — Redis is a cache,
not a source of truth. Callers fall back to "fresh" state when load
fails, and skip remembering the latest turn when append fails.
The companion archive in pet_message (Postgres) is the durable record.
"""
from __future__ import annotations

import json

from redis.asyncio import Redis

KEY_PREFIX = "pet:ctx:"
DEFAULT_MAX_TURNS = 10
DEFAULT_TTL_SEC = 7200


def _key(visitor_hash: str) -> str:
    return f"{KEY_PREFIX}{visitor_hash}"


async def load(
    redis: Redis,
    visitor_hash: str,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> list[dict]:
    """Return prior turns oldest-first, at most 2*max_turns members."""
    cap = max_turns * 2
    raw = await redis.lrange(_key(visitor_hash), 0, cap - 1)
    out: list[dict] = []
    for s in reversed(list(raw)):
        try:
            out.append(json.loads(s))
        except (TypeError, ValueError):
            continue
    return out


async def append(
    redis: Redis,
    visitor_hash: str,
    *,
    user_turn: dict,
    assistant_turn: dict,
    max_turns: int = DEFAULT_MAX_TURNS,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> None:
    """Atomically prepend user+assistant, trim, and reset TTL."""
    key = _key(visitor_hash)
    cap = max_turns * 2 - 1
    # The list is newest-first (LPUSH). Push user first, then assistant,
    # so assistant ends up at index 0 (most recent) and user at index 1.
    # load() reverses the list to yield chronological [user, assistant].
    pipe = redis.pipeline()
    pipe.lpush(key, json.dumps(user_turn, ensure_ascii=False))
    pipe.lpush(key, json.dumps(assistant_turn, ensure_ascii=False))
    pipe.ltrim(key, 0, cap)
    pipe.expire(key, ttl_sec)
    await pipe.execute()


async def clear(redis: Redis, visitor_hash: str) -> None:
    await redis.delete(_key(visitor_hash))
