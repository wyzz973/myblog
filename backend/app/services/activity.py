"""Activity stream queries over event_log."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog


async def list_events(
    s: AsyncSession,
    *,
    types: list[str] | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EventLog]:
    """List event_log rows newest-first.

    Task 45: ``q`` does case-insensitive substring matching on
    ``actor`` OR ``target`` so owners can find events touching a
    particular email / post id / token name without scrolling.
    Whitespace-only ``q`` is ignored.
    """
    stmt = select(EventLog).order_by(EventLog.created_at.desc()).limit(limit).offset(offset)
    if types:
        stmt = stmt.where(EventLog.type.in_(types))
    if q and q.strip():
        like = f"%{q.strip()}%"
        # `target` is nullable — `coalesce` would normalize, but ILIKE on a
        # NULL just returns NULL (treated as false in WHERE) so the OR
        # branch silently no-ops for rows without a target. That's the
        # behavior we want.
        stmt = stmt.where(or_(EventLog.actor.ilike(like), EventLog.target.ilike(like)))
    return list((await s.execute(stmt)).scalars().all())
