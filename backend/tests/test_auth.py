from datetime import timedelta

import pytest

from app.services.auth import create_access_token, decode_access_token, AuthError


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
