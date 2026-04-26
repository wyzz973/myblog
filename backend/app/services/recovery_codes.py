"""8-of-8 recovery codes for 2FA fallback.

Format: 4 + 4 chars from Crockford-base32 alphabet (excludes I/L/O/U for
human transcription). Stored as sha256 hex. Single-use.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TfaRecoveryCode

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford-base32 (no ILOU)


def _generate_one() -> str:
    pick = lambda: "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"{pick()}-{pick()}"


def generate_set() -> list[str]:
    """Return 8 distinct codes."""
    seen: set[str] = set()
    while len(seen) < 8:
        seen.add(_generate_one())
    return list(seen)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode()).hexdigest()


async def replace_for_account(s: AsyncSession, *, account_id: int) -> list[str]:
    """Wipe existing codes for an account and persist a fresh set of 8.

    Returns the raw codes (caller shows them ONCE in the response).
    """
    await s.execute(delete(TfaRecoveryCode).where(TfaRecoveryCode.account_id == account_id))
    raw = generate_set()
    for code in raw:
        s.add(
            TfaRecoveryCode(
                code_hash=hash_code(code),
                account_id=account_id,
                created_at=datetime.now(UTC),
            )
        )
    return raw


async def verify_and_consume(
    s: AsyncSession, *, account_id: int, presented: str
) -> bool:
    """Mark a recovery code as used. Returns True on first-and-only success."""
    target = hash_code(presented)
    row = (
        await s.execute(
            select(TfaRecoveryCode).where(
                TfaRecoveryCode.code_hash == target,
                TfaRecoveryCode.account_id == account_id,
                TfaRecoveryCode.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await s.execute(
        update(TfaRecoveryCode)
        .where(TfaRecoveryCode.code_hash == target)
        .values(used_at=datetime.now(UTC))
    )
    return True
