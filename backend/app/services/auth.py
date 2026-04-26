"""Auth helpers — password hashing, JWT access tokens, Redis refresh tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.asyncio import Redis

from app.config import get_settings
from app.errors import AuthError

_hasher = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4)
_settings = get_settings()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    try:
        _hasher.verify(stored_hash, plain)
        return True
    except VerifyMismatchError:
        return False


def _new_jti() -> str:
    return secrets.token_urlsafe(16)


def create_access_token(*, sub: str, email: str, ttl: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (ttl or timedelta(seconds=_settings.access_token_ttl))
    return jwt.encode(
        {
            "sub": sub,
            "email": email,
            "jti": _new_jti(),
            "iat": datetime.now(UTC),
            "exp": expires,
        },
        _settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid token") from e


# ----- Refresh tokens (Redis-backed, rotated on use) -----------------------

def _refresh_key(sub: str, jti: str) -> str:
    return f"refresh:{sub}:{jti}"


def _hash_raw(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh(redis: Redis, *, sub: str) -> tuple[str, str]:
    """Generate a fresh refresh token. Returns (raw, jti).

    Stores `refresh:{sub}:{jti}` -> sha256(raw) in Redis with the configured TTL.
    The jti is what callers embed in cookies/round-trips for lookup.
    """
    raw = secrets.token_urlsafe(32)
    jti = _new_jti()
    await redis.set(
        _refresh_key(sub, jti),
        _hash_raw(raw),
        ex=_settings.refresh_token_ttl,
    )
    return raw, jti


async def rotate_refresh(
    redis: Redis, *, sub: str, presented_raw: str
) -> tuple[str, str] | None:
    """Find the jti whose hash matches presented_raw, delete it, issue a new one.

    Single-author scale: O(n) scan over `refresh:{sub}:*` is fine. Returns
    None if no match (caller should treat as 401 + clear cookie).
    """
    target = _hash_raw(presented_raw)
    pattern = f"refresh:{sub}:*"
    async for key in redis.scan_iter(match=pattern):
        if (await redis.get(key)) == target:
            await redis.delete(key)
            return await issue_refresh(redis, sub=sub)
    return None


async def revoke_refresh(redis: Redis, *, sub: str, jti: str) -> None:
    await redis.delete(_refresh_key(sub, jti))


async def revoke_all_refresh(redis: Redis, *, sub: str) -> None:
    """Used on password change or admin force-logout."""
    pattern = f"refresh:{sub}:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)
