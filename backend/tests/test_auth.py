from datetime import timedelta

import pytest

from app.services.auth import (
    AuthError,
    create_access_token,
    decode_access_token,
    issue_refresh,
    revoke_refresh,
    rotate_refresh,
)


def test_token_round_trip():
    token = create_access_token(sub="1", email="hi@a.dev")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "hi@a.dev"


def test_token_expired_raises():
    token = create_access_token(sub="1", email="hi@a.dev", ttl=timedelta(seconds=-5))
    with pytest.raises(AuthError):
        decode_access_token(token)


def test_token_tampered_raises():
    token = create_access_token(sub="1", email="hi@a.dev")
    bad = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(AuthError):
        decode_access_token(bad)


def test_access_token_includes_jti():
    tok = create_access_token(sub="1", email="a@b.c")
    payload = decode_access_token(tok)
    assert "jti" in payload
    assert len(payload["jti"]) >= 16


async def test_issue_refresh_persists_in_redis(redis):
    raw, jti = await issue_refresh(redis, sub="1")
    assert len(raw) >= 32
    assert await redis.exists(f"refresh:1:{jti}")


async def test_rotate_refresh_invalidates_old(redis):
    raw, jti = await issue_refresh(redis, sub="1")
    new_raw, new_jti = await rotate_refresh(redis, sub="1", presented_raw=raw)
    assert new_raw != raw
    assert new_jti != jti
    assert not await redis.exists(f"refresh:1:{jti}")
    assert await redis.exists(f"refresh:1:{new_jti}")


async def test_rotate_refresh_unknown_returns_none(redis):
    result = await rotate_refresh(redis, sub="1", presented_raw="bogus")
    assert result is None


async def test_revoke_refresh(redis):
    raw, jti = await issue_refresh(redis, sub="1")
    await revoke_refresh(redis, sub="1", jti=jti)
    assert not await redis.exists(f"refresh:1:{jti}")
