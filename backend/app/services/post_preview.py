"""Signed preview tokens for unpublished posts.

The token grants temporary read access to a single draft/scheduled post
through the public detail endpoint. We sign with HMAC-SHA256 over the
fixed-width payload `preview:{post_id}:{exp_ts}` and append the digest;
the public endpoint reverses the verification before bypassing the
status filter.

Tokens are stateless (no DB row) so revocation is "let it expire" —
TTL is 24h, short enough that a leaked link can't haunt the owner.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

PREVIEW_TTL_SECONDS = 24 * 60 * 60
_VERSION = "v1"


def _sign(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_preview_token(*, secret: str, post_id: str, ttl_seconds: int = PREVIEW_TTL_SECONDS) -> tuple[str, int]:
    """Return (token, expires_unix_seconds).

    Token format: `v1.{post_id}.{exp_ts}.{sig}`. The signature covers
    everything before it so the bot can't tweak the post_id or exp.
    """
    if not secret or len(secret) < 16:
        raise ValueError("secret too short")
    exp = int(time.time()) + max(60, int(ttl_seconds))
    payload = f"{_VERSION}.{post_id}.{exp}"
    sig = _sign(secret, payload)
    return f"{payload}.{sig}", exp


def verify_preview_token(*, secret: str, token: str, post_id: str) -> bool:
    """Return True iff `token` is a fresh, intact signature for `post_id`."""
    if not token or not secret:
        return False
    parts = token.split(".")
    if len(parts) != 4:
        return False
    version, tok_id, tok_exp, sig = parts
    if version != _VERSION or tok_id != post_id:
        return False
    try:
        exp = int(tok_exp)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    expected = _sign(secret, f"{version}.{tok_id}.{tok_exp}")
    return hmac.compare_digest(expected, sig)
