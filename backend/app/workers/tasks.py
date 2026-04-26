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


from app.services.markdown_pipeline import compute_derived, parse_markdown  # noqa: E402


async def recompute_post_word_counts(ctx: dict) -> dict:
    """Recompute word_count for every post from body_md."""
    async with AsyncSessionLocal() as s:
        posts = (await s.execute(select(Post.id, Post.body_md))).all()
        n = 0
        for pid, body_md in posts:
            blocks = parse_markdown(body_md)
            derived = compute_derived(blocks)
            await s.execute(
                update(Post).where(Post.id == pid).values(word_count=derived["word_count"])
            )
            n += 1
        await s.commit()
        return {"updated": n}


from app.models import ContribDay  # noqa: E402
from app.services import github as github_svc  # noqa: E402
from app.services import integrations as integrations_svc  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402


async def sync_github_contrib(ctx: dict) -> dict:
    """Pull latest 52-week contribution calendar; upsert contrib_days."""
    async with AsyncSessionLocal() as s:
        row = await integrations_svc.get(s, name="github")
        if row is None or row.username is None:
            return {"count": 0, "skipped": "no integration configured"}
        token = await integrations_svc.get_secret(s, name="github")
        if token is None:
            return {"count": 0, "skipped": "no token"}

    try:
        days = await github_svc.fetch_contributions(token, row.username)
    except Exception as e:  # noqa: BLE001
        async with AsyncSessionLocal() as s:
            await integrations_svc.set_status(s, name="github", status="failed", error=str(e)[:512])
            await s.commit()
        raise

    async with AsyncSessionLocal() as s:
        for d in days:
            stmt = pg_insert(ContribDay).values(
                day=d["day"], count=d["count"], level=d["level"],
            ).on_conflict_do_update(
                index_elements=[ContribDay.day],
                set_={"count": d["count"], "level": d["level"]},
            )
            await s.execute(stmt)
        await integrations_svc.set_status(s, name="github", status="ok", error=None)
        await s.commit()

    return {"count": len(days), "days_with_activity": sum(1 for d in days if d["count"] > 0)}
