"""SHA-256 hashing helpers for IP and email values that must NEVER persist
in raw form (privacy + GDPR-light hygiene).

Both helpers concatenate the input with `LIKE_SALT` using a `|` separator
so that no two distinct (input, salt) pairs can hash to the same digest
through a clever boundary collision.
"""
from __future__ import annotations

import hashlib

from app.config import get_settings


def _hash(parts: tuple[str, str]) -> str:
    return hashlib.sha256(f"{parts[0]}|{parts[1]}".encode()).hexdigest()


def ip_hash(ip: str) -> str:
    """sha256(ip|LIKE_SALT) hex (64 chars)."""
    return _hash((ip, get_settings().like_salt))


def email_hash(email: str) -> str:
    """sha256(email_normalised|LIKE_SALT) hex.

    Normalisation: lowercase + strip whitespace.
    """
    normalised = email.lower().strip()
    return _hash((normalised, get_settings().like_salt))
