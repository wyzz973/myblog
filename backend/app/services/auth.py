"""Auth helpers — password hashing and JWT access tokens."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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


def create_access_token(*, sub: str, email: str, ttl: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (ttl or timedelta(seconds=_settings.access_token_ttl))
    return jwt.encode(
        {"sub": sub, "email": email, "iat": datetime.now(UTC), "exp": expires},
        _settings.jwt_secret, algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid token") from e
