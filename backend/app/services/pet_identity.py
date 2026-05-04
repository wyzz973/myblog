"""Anonymous signed visitor identity for the public pet."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import get_settings
from app.services.hashing import ip_hash

COOKIE_NAME = "pet_vid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _salt() -> bytes:
    return get_settings().like_salt.encode()


def new_vid() -> str:
    return secrets.token_urlsafe(24)


def sign_vid(vid: str) -> str:
    tag = hmac.new(_salt(), vid.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{vid}|{tag}"


def verify_vid(value: str | None) -> str | None:
    if not value or "|" not in value:
        return None
    vid, _, tag = value.partition("|")
    if not vid or len(tag) != 16:
        return None
    expected = sign_vid(vid).split("|", 1)[1]
    if not hmac.compare_digest(tag, expected):
        return None
    return vid


def hash_vid(vid: str) -> str:
    return hmac.new(_salt(), vid.encode(), hashlib.sha256).hexdigest()[:16]


def visitor_hash_from_parts(*, signed_vid: str | None, ip: str) -> str:
    vid = verify_vid(signed_vid)
    if vid:
        return hash_vid(vid)
    return ip_hash(ip)[:16]


def ensure_signed_vid(value: str | None) -> tuple[str, str, bool]:
    vid = verify_vid(value)
    if vid:
        return sign_vid(vid), hash_vid(vid), False
    vid = new_vid()
    return sign_vid(vid), hash_vid(vid), True
