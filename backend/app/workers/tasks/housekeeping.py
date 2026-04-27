"""ARQ task: prune_event_log."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import EventLog


async def prune_event_log(ctx: dict) -> dict:
    """Hard-delete event_log rows older than 90 days. Archive table is P7 work."""
    cutoff = datetime.now(UTC) - timedelta(days=90)
    async with AsyncSessionLocal() as s:
        res = await s.execute(delete(EventLog).where(EventLog.created_at < cutoff))
        await s.commit()
        return {"deleted": res.rowcount}
