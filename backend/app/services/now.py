"""Now-entries service. set_current handles transactional flip."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NowEntry


async def list_all(s: AsyncSession, *, limit: int = 100) -> list[NowEntry]:
    return list((
        await s.execute(select(NowEntry).order_by(NowEntry.created_at.desc()).limit(limit))
    ).scalars().all())


async def get_current(s: AsyncSession) -> NowEntry | None:
    return (
        await s.execute(select(NowEntry).where(NowEntry.is_current.is_(True)))
    ).scalar_one_or_none()


async def history(s: AsyncSession, *, limit: int = 10) -> list[NowEntry]:
    return list((
        await s.execute(
            select(NowEntry).where(NowEntry.is_current.is_(False))
            .order_by(NowEntry.created_at.desc()).limit(limit)
        )
    ).scalars().all())


async def create(
    s: AsyncSession, *, body_md: str, listening: str | None,
    reading: str | None, is_current: bool,
) -> NowEntry:
    if is_current:
        await s.execute(update(NowEntry).where(NowEntry.is_current.is_(True)).values(is_current=False))
        await s.flush()
    row = NowEntry(
        body_md=body_md, listening=listening, reading=reading,
        is_current=is_current, created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def patch(
    s: AsyncSession, *, entry_id: int,
    body_md: str | None, listening: str | None,
    reading: str | None, is_current: bool | None,
) -> NowEntry | None:
    row = (
        await s.execute(select(NowEntry).where(NowEntry.id == entry_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    if body_md is not None:
        row.body_md = body_md
    if listening is not None:
        row.listening = listening
    if reading is not None:
        row.reading = reading
    if is_current is True and not row.is_current:
        await s.execute(update(NowEntry).where(NowEntry.is_current.is_(True)).values(is_current=False))
        await s.flush()
        row.is_current = True
    elif is_current is False:
        row.is_current = False
    await s.flush()
    await s.refresh(row)
    return row


async def delete_one(s: AsyncSession, *, entry_id: int) -> bool:
    res = await s.execute(delete(NowEntry).where(NowEntry.id == entry_id))
    await s.flush()
    return res.rowcount > 0
