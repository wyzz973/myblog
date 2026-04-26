"""ARQ task implementations."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def send_email_task(ctx: dict, *, to: str, subject: str, body: str) -> dict:
    """Run smtplib send in a thread; ARQ handles retry-with-backoff.

    On exception, ARQ records the failure; we also log a WARNING so the
    failure is visible in structlog output.
    """
    from app.services.email import _send_sync
    try:
        await asyncio.to_thread(_send_sync, to=to, subject=subject, body=body)
        log.info("email.sent", to=to, subject=subject)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        log.warning("email.send_failed", to=to, subject=subject, error=str(e))
        # raise so ARQ retries (3 attempts default with backoff)
        raise


# job-level retry config (ARQ reads these from the function)
send_email_task.max_tries = 3


from datetime import UTC, datetime as _dt  # noqa: E402

from sqlalchemy import select, update  # noqa: E402

from app.db import AsyncSessionLocal  # noqa: E402
from app.models import Post  # noqa: E402
from app.services.event_log import write_event  # noqa: E402


async def publish_scheduled_posts(ctx: dict) -> dict:
    """Flip status='scheduled' AND scheduled_at <= now() to 'published'."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Post.id).where(
                Post.status == "scheduled",
                Post.scheduled_at <= _dt.now(UTC),
            )
        )).scalars().all()
        if not rows:
            return {"count": 0}
        await s.execute(
            update(Post)
            .where(Post.id.in_(rows))
            .values(status="published")
        )
        for pid in rows:
            await write_event(
                s, type="post.published", actor="worker",
                target=pid, meta={"from": "scheduled"},
            )
        await s.commit()
        return {"count": len(rows)}


from datetime import timedelta  # noqa: E402

from app.models import MagicLink as _MagicLink  # noqa: E402


async def cleanup_expired_magic_links(ctx: dict) -> dict:
    """Delete magic_links rows that are expired or already consumed."""
    from sqlalchemy import or_, delete as sa_delete
    async with AsyncSessionLocal() as s:
        res = await s.execute(
            sa_delete(_MagicLink).where(
                or_(
                    _MagicLink.expires_at < _dt.now(UTC),
                    _MagicLink.consumed_at.is_not(None),
                )
            )
        )
        await s.commit()
        return {"count": res.rowcount}


from app.models import EventLog as _EventLog  # noqa: E402


async def prune_event_log(ctx: dict) -> dict:
    """Hard-delete event_log rows older than 90 days. Archive table is P7 work."""
    from sqlalchemy import delete as sa_delete
    cutoff = _dt.now(UTC) - timedelta(days=90)
    async with AsyncSessionLocal() as s:
        res = await s.execute(sa_delete(_EventLog).where(_EventLog.created_at < cutoff))
        await s.commit()
        return {"deleted": res.rowcount}
