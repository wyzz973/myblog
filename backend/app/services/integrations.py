"""Integrations: encrypted CRUD over the integrations table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Integration
from app.services import secret_box


async def upsert(
    s: AsyncSession,
    *,
    name: Literal["github", "anthropic"],
    username: str | None = None,
    secret: str,
    extra: dict[str, Any] | None = None,
) -> Integration:
    """Insert or update the integrations row. Encrypts `secret` before storage."""
    existing = (
        await s.execute(select(Integration).where(Integration.name == name))
    ).scalar_one_or_none()
    encrypted = secret_box.encrypt(secret)
    now = datetime.now(UTC)
    if existing is None:
        row = Integration(
            name=name, username=username, secret_encrypted=encrypted,
            extra_json=extra or {}, created_at=now, updated_at=now,
        )
        s.add(row)
    else:
        existing.username = username
        existing.secret_encrypted = encrypted
        if extra is not None:
            existing.extra_json = extra
        existing.updated_at = now
        row = existing
    await s.flush()
    return row


async def get(s: AsyncSession, *, name: str) -> Integration | None:
    return (
        await s.execute(select(Integration).where(Integration.name == name))
    ).scalar_one_or_none()


async def get_secret(s: AsyncSession, *, name: str) -> str | None:
    row = await get(s, name=name)
    if row is None:
        return None
    return secret_box.decrypt(row.secret_encrypted)


async def set_status(
    s: AsyncSession,
    *,
    name: str,
    status: Literal["ok", "failed"],
    error: str | None,
) -> None:
    await s.execute(
        update(Integration)
        .where(Integration.name == name)
        .values(
            last_synced_at=datetime.now(UTC),
            last_status=status,
            last_error=error,
            updated_at=datetime.now(UTC),
        )
    )
    await s.flush()
