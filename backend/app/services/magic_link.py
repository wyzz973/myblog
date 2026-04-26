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
    """Mark link consumed and return the associated Account, or None on miss/expired/used."""
    row = (
        await s.execute(select(MagicLink).where(MagicLink.token_hash == _hash(raw)))
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.consumed_at is not None:
        return None
    if row.expires_at < datetime.now(UTC):
        return None
    await s.execute(
        update(MagicLink)
        .where(MagicLink.token_hash == row.token_hash)
        .values(consumed_at=datetime.now(UTC))
    )
    acct = (
        await s.execute(select(Account).where(Account.id == row.account_id))
    ).scalar_one_or_none()
    return acct
