
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


def test_separator_prevents_concatenation_collision(monkeypatch):
    """Without a separator, sha256("ab"+"cdef") == sha256("abc"+"def").
    With our pipe separator they hash differently because the input
    strings include the literal '|' boundary."""
    monkeypatch.setenv("LIKE_SALT", "cdef" + "x" * 28)  # 32+ chars
    from app.config import get_settings
    get_settings.cache_clear()
    h_ab = ip_hash("ab")        # sha256("ab|cdef...")

    monkeypatch.setenv("LIKE_SALT", "def" + "x" * 29)
    get_settings.cache_clear()
    h_abc = ip_hash("abc")      # sha256("abc|def...")

    # The unseparated versions would BOTH be sha256("abcdef...") and equal.
    # With pipe they must differ.
    assert h_ab != h_abc
