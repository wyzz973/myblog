"""Activity stream queries over event_log."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog


async def list_events(
    s: AsyncSession,
    *,
    types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EventLog]:
    q = select(EventLog).order_by(EventLog.created_at.desc()).limit(limit).offset(offset)
    if types:
        q = q.where(EventLog.type.in_(types))
    return list((await s.execute(q)).scalars().all())
