"""Hit beacon write path: filter (UA bot, Redis dedup) + INSERT."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HitEvent, Post

BOT_RE = re.compile(
    r"(bot|crawler|spider|curl|wget|httpclient|python-requests)", re.I
)
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_DEDUP_TTL = 60  # seconds


def _bot(ua: str | None) -> bool:
    return bool(ua and BOT_RE.search(ua))


def _normalize_country(country: str | None) -> str | None:
    if country is None:
        return None
    return country if _COUNTRY_RE.match(country) else None


def _dedup_key(ip: str, path: str) -> str:
    h = hashlib.sha256(f"{ip}|{path}".encode()).hexdigest()[:16]
    return f"hit:{h}"


async def _post_exists(s: AsyncSession, post_id: str) -> bool:
    exists = await s.execute(select(Post.id).where(Post.id == post_id))
    return exists.scalar_one_or_none() is not None


async def record(
    s: AsyncSession,
    *,
    redis,
    path: str,
    referrer: str | None,
    ip: str,
    country: str | None,
    user_agent: str | None,
    post_id: str | None,
) -> bool:
    """Persist one hit. Returns True if recorded, False if filtered.

    Filters in order: UA bot regex → Redis 60s dedup on hash(ip|path).
    Validates post_id (NULL if not in posts table) and country (NULL if not 2-letter ASCII upper).
    Never writes IP / UA / raw user_agent to DB.
    """
    if _bot(user_agent):
        return False

    key = _dedup_key(ip, path)
    set_ok = await redis.set(key, "1", ex=_DEDUP_TTL, nx=True)
    if not set_ok:
        return False

    if post_id is not None and not await _post_exists(s, post_id):
        post_id = None

    s.add(HitEvent(
        path=path[:512],
        referrer=(referrer[:512] if referrer else None),
        country=_normalize_country(country),
        post_id=post_id,
        created_at=datetime.now(UTC),
    ))
    await s.flush()
    return True
