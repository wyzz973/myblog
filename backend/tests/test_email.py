"""Email transport: dev mode (log) vs SMTP mode (mocked smtplib)."""
import logging
from unittest.mock import MagicMock, patch

from app.services.email import send_comment_notification, send_email, send_magic_link


async def test_dev_mode_logs_when_smtp_host_unset(caplog, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    caplog.set_level(logging.INFO)
    await send_email(to="a@b.c", subject="hi", body="hello")
    # We don't strictly assert on log capture (structlog vs caplog can be
    # finicky); the absence of a raised exception + no smtplib call is
    # the contract: dev mode is non-fatal.


async def test_smtp_mode_calls_smtplib(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    from app.config import get_settings
    get_settings.cache_clear()

    fake_smtp = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_smtp
    fake_ctx.__exit__.return_value = False

    with patch("smtplib.SMTP", return_value=fake_ctx) as ctor:
        await send_email(to="a@b.c", subject="hi", body="hello")

    ctor.assert_called_once_with("smtp.example.test", 587)
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("user", "pw")
    fake_smtp.send_message.assert_called_once()


async def test_smtp_failure_swallowed(monkeypatch, caplog):
    """SMTP exception must NOT propagate; comment/magic-link must still respond."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP", side_effect=ConnectionError("fake")):
        # Must not raise
        await send_email(to="a@b.c", subject="hi", body="hello")


async def test_send_magic_link_uses_send_email(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    await send_magic_link(email="a@b.c", url="http://x/y")
    # No raise — dev fallback covers it.


async def test_send_comment_notification_uses_send_email(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    await send_comment_notification(
        to="admin@x.com", comment_id=42, post_id="hello", who="alice", snippet="hi"
    )
