"""Short Redis cache for repeat low-risk pet answers."""
from __future__ import annotations

import hashlib
import json

from redis.asyncio import Redis

from app.services import pet_archive

CACHE_TTL_SECONDS = 20 * 60


def _hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def cache_key(
    *,
    mode: str,
    post_id: str | None,
    selection: str | None,
    message: str | None,
) -> str:
    return "pet:cache:" + ":".join([
        mode,
        post_id or "-",
        _hash(selection),
        _hash(message),
    ])


def cacheable(*, source: str, reply: str, selection: str | None, message: str | None) -> bool:
    if source in ("fallback", "rate_limited", "cache"):
        return False
    if not reply or len(reply) > 500:
        return False
    joined = "\n".join([selection or "", message or ""])
    return pet_archive.sanitize_text(joined, max_chars=len(joined) + 20) == joined


async def get(redis: Redis, key: str) -> str | None:
    raw = await redis.get(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    text = data.get("reply")
    return text if isinstance(text, str) and text else None


async def set(redis: Redis, key: str, reply: str) -> None:
    await redis.set(key, json.dumps({"reply": reply}, ensure_ascii=False), ex=CACHE_TTL_SECONDS)
