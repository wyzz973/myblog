"""API tokens (long-lived bearer tokens for external scripts/CLI).

Raw form: 'tk_' + 32 url-safe-b64 bytes (~43 chars).
Stored: sha256 hex (single-author scale; 256-bit entropy renders bcrypt
work-factor unnecessary, see spec §6.3 deviation note).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiToken

PREFIX = "tk_"


def generate_raw() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def hash_raw(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create(
    s: AsyncSession,
    *,
    name: str,
    scope: Literal["read", "write"],
) -> tuple[ApiToken, str]:
    raw = generate_raw()
    row = ApiToken(
        name=name,
        scope=scope,
        token_hash=hash_raw(raw),
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.commit()
    await s.refresh(row)
    return row, raw


async def verify(s: AsyncSession, raw: str) -> ApiToken | None:
    """Verify the bearer token without writing last_used_at."""
    if not raw.startswith(PREFIX):
        return None
    return (
        await s.execute(
            select(ApiToken).where(
                ApiToken.token_hash == hash_raw(raw),
                ApiToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def touch_last_used(s: AsyncSession, *, token_id: int) -> None:
    """Stamp last_used_at AND increment usage_count atomically.

    Uses SQL `usage_count = usage_count + 1` so concurrent requests
    against the same token don't lose updates (which a read-modify-write
    in Python would).
    """
    await s.execute(
        update(ApiToken)
        .where(ApiToken.id == token_id)
        .values(
            last_used_at=datetime.now(UTC),
            usage_count=ApiToken.usage_count + 1,
        )
    )
    await s.commit()


async def revoke(s: AsyncSession, *, token_id: int) -> bool:
    res = await s.execute(
        update(ApiToken)
        .where(ApiToken.id == token_id, ApiToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await s.commit()
    return res.rowcount > 0
