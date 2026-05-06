"""Magic-link email rotation (Task 28c).

Two-step flow:
  1. issue() — current owner submits new email + password; a row is added
     with a hashed one-shot token, and the raw token is mailed to the new
     address. Old email keeps working.
  2. consume() — confirmation endpoint atomically marks the row consumed,
     returns the (account_id, new_email) so the caller can update Account.

Same single-use guarantee as magic_link.consume: WHERE consumed_at IS NULL
on the UPDATE means concurrent confirms can never both succeed.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PendingEmailChange


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue(
    s: AsyncSession,
    *,
    account_id: int,
    new_email: str,
    requested_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Generate token, persist pending row, return raw token (caller mails it)."""
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    s.add(
        PendingEmailChange(
            token_hash=_hash(raw),
            account_id=account_id,
            new_email=new_email,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.magic_link_ttl),
            requested_ip=requested_ip,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
    )
    return raw


async def consume(s: AsyncSession, *, raw: str) -> tuple[int, str] | None:
    """Atomically mark the row consumed; returns (account_id, new_email)
    or None if token is unknown / expired / already consumed."""
    res = await s.execute(
        update(PendingEmailChange)
        .where(PendingEmailChange.token_hash == _hash(raw))
        .where(PendingEmailChange.consumed_at.is_(None))
        .where(PendingEmailChange.expires_at > datetime.now(UTC))
        .values(consumed_at=datetime.now(UTC))
        .returning(PendingEmailChange.account_id, PendingEmailChange.new_email)
    )
    row = res.first()
    if row is None:
        return None
    return int(row[0]), str(row[1])
