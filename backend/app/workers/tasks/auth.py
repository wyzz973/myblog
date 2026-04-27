"""ARQ task: cleanup_expired_magic_links."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_

from app.db import AsyncSessionLocal
from app.models import MagicLink


async def cleanup_expired_magic_links(ctx: dict) -> dict:
    """Delete magic_links rows that are expired or already consumed."""
    async with AsyncSessionLocal() as s:
        res = await s.execute(
            delete(MagicLink).where(
                or_(
                    MagicLink.expires_at < datetime.now(UTC),
                    MagicLink.consumed_at.is_not(None),
                )
            )
        )
        await s.commit()
        return {"count": res.rowcount}
