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
    """INSERT ... ON CONFLICT DO NOTHING. Caller is responsible for commit.

    Returns (current_total_likes_after_flush, was_new).
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
    await s.flush()
    total = await get_count(s, post_id=post_id)
    return total, was_new


async def get_count(s: AsyncSession, *, post_id: str) -> int:
    res = await s.execute(
        select(func.count(LikeEvent.id)).where(LikeEvent.post_id == post_id)
    )
    return int(res.scalar() or 0)


async def get_counts(
    s: AsyncSession, *, post_ids: list[str]
) -> dict[str, int]:
    """Batch lookup so list-style admin/public endpoints can fill a likes
    column without N+1 queries. Posts with zero likes are returned as 0.
    """
    if not post_ids:
        return {}
    res = await s.execute(
        select(LikeEvent.post_id, func.count(LikeEvent.id))
        .where(LikeEvent.post_id.in_(post_ids))
        .group_by(LikeEvent.post_id)
    )
    counts: dict[str, int] = {pid: 0 for pid in post_ids}
    for pid, n in res.all():
        counts[pid] = int(n)
    return counts
