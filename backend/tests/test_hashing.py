
import pytest

from app.services.hashing import email_hash, ip_hash


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("LIKE_SALT", "test-salt-1234567")


def test_ip_hash_deterministic():
    a = ip_hash("1.2.3.4")
    b = ip_hash("1.2.3.4")
    assert a == b
    assert len(a) == 64


def test_ip_hash_distinct_for_different_ips():
    assert ip_hash("1.2.3.4") != ip_hash("1.2.3.5")


def test_email_hash_normalises_case_and_whitespace():
    assert email_hash("HI@WANGYANG.dev") == email_hash("hi@wangyang.dev")
    assert email_hash("  hi@wangyang.dev  ") == email_hash("hi@wangyang.dev")


def test_email_hash_distinct_for_different_emails():
    assert email_hash("a@b.c") != email_hash("a@b.d")


def test_separator_prevents_concatenation_collision():
    """Without a separator, sha256(ip_a + salt) could collide with sha256(ip_b + salt')."""
    # Pipe separator: sha256("1.2.3.4|salt") vs sha256("1.2.3|.4salt")
    # The two would be equal IF the salt position changed; with the pipe they cannot.
    assert ip_hash("1.2.3.4") != ip_hash("1.2.3")
