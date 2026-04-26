"""Magic-link login: opaque token, sha256 stored, 15-min TTL, single-use."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models import Account, MagicLink


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue(
    s: AsyncSession,
    *,
    account_id: int,
    requested_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Generate, persist, return raw token (caller embeds in URL → email)."""
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    s.add(
        MagicLink(
            token_hash=_hash(raw),
            account_id=account_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.magic_link_ttl),
            requested_ip=requested_ip,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
    )
    await s.commit()
    return raw


async def issue_for_test(
    *, s_factory: async_sessionmaker[AsyncSession], account_id: int
) -> str:
    """Test helper that bypasses the email log path."""
    async with s_factory() as s:
        return await issue(s, account_id=account_id)


async def consume(s: AsyncSession, *, raw: str) -> Account | None:
    """Atomically mark consumed and return Account. Single UPDATE with predicates
    so concurrent calls can never both succeed (DB-level single-use guarantee)."""
    res = await s.execute(
        update(MagicLink)
        .where(MagicLink.token_hash == _hash(raw))
        .where(MagicLink.consumed_at.is_(None))
        .where(MagicLink.expires_at > datetime.now(UTC))
        .values(consumed_at=datetime.now(UTC))
        .returning(MagicLink.account_id)
    )
    row = res.first()
    if row is None:
        return None
    account_id = row[0]
    return (
        await s.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
