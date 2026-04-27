"""ARQ tasks: post lifecycle (publish_scheduled_posts, recompute_post_word_counts)."""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update

from app.db import AsyncSessionLocal
from app.models import Post
from app.services.event_log import write_event
from app.services.markdown_pipeline import compute_derived, parse_markdown

log = structlog.get_logger(__name__)


async def publish_scheduled_posts(ctx: dict) -> dict:
    """Atomically flip status='scheduled' AND scheduled_at <= now() to 'published'.

    Uses UPDATE ... RETURNING so a second concurrent worker run sees zero rows
    rather than the same id list — preventing duplicate `post.published` events.
    """
    async with AsyncSessionLocal() as s:
        res = await s.execute(
            update(Post)
            .where(
                Post.status == "scheduled",
                Post.scheduled_at <= datetime.now(UTC),
            )
            .values(status="published")
            .returning(Post.id)
        )
        ids = [r[0] for r in res.all()]
        if not ids:
            return {"count": 0}
        for pid in ids:
            await write_event(
                s, type="post.published", actor="worker",
                target=pid, meta={"from": "scheduled"},
            )
        await s.commit()
        return {"count": len(ids)}


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
