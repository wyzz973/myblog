"""Likes service: idempotent per (post_id, ip_hash, day) UNIQUE constraint."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LikeEvent
from app.services.hashing import ip_hash


async def record_like(
    s: AsyncSession, *, post_id: str, ip: str
) -> tuple[int, bool]:
    """INSERT ... ON CONFLICT DO NOTHING.

    Returns (current total likes for the post, was_new).
    """
    today = datetime.now(UTC).date()
    stmt = (
        pg_insert(LikeEvent)
        .values(
            post_id=post_id,
            ip_hash=ip_hash(ip),
            day=today,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(constraint="uq_like_events_post_ip_day")
        .returning(LikeEvent.id)
    )
    res = await s.execute(stmt)
    inserted_id = res.scalar_one_or_none()
    was_new = inserted_id is not None
    await s.commit()
    total = await get_count(s, post_id=post_id)
    return total, was_new


async def get_count(s: AsyncSession, *, post_id: str) -> int:
    res = await s.execute(
        select(func.count(LikeEvent.id)).where(LikeEvent.post_id == post_id)
    )
    return int(res.scalar() or 0)
