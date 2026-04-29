"""ARQ task: prune_event_log.

Three-step retention pipeline (idempotent):

1. Copy ``event_log`` rows older than 90 days into ``event_log_archive``.
2. Delete those source rows from ``event_log``.
3. Drop ``event_log_archive`` rows older than 365 days.

Re-running the task is safe: step 2 removes the just-copied source rows so
the next run will not re-archive them, and step 3 only deletes archive rows
beyond the 1-year window.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import EventLog, EventLogArchive


async def prune_event_log(ctx: dict) -> dict:
    """Archive >90d event_log rows; drop archive rows >365d."""
    now = datetime.now(UTC)
    archive_cutoff = now - timedelta(days=90)
    drop_cutoff = now - timedelta(days=365)

    async with AsyncSessionLocal() as s:
        # Step 1: select source rows older than 90d
        rows = (
            await s.execute(
                select(EventLog).where(EventLog.created_at < archive_cutoff)
            )
        ).scalars().all()

        archived = 0
        if rows:
            s.add_all(
                [
                    EventLogArchive(
                        type=row.type,
                        actor=row.actor,
                        target=row.target,
                        meta=row.meta,
                        created_at=row.created_at,
                    )
                    for row in rows
                ]
            )
            await s.flush()
            archived = len(rows)

            # Step 2: delete the just-archived source rows
            await s.execute(
                delete(EventLog).where(EventLog.created_at < archive_cutoff)
            )

        # Step 3: prune archive rows older than 365d
        prune_res = await s.execute(
            delete(EventLogArchive).where(EventLogArchive.created_at < drop_cutoff)
        )
        archive_pruned = prune_res.rowcount or 0

        await s.commit()

    return {"archived": archived, "archive_pruned": archive_pruned}
