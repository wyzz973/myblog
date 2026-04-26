"""Inline-mode end-to-end: enqueue → task → smtplib mock receives send_message."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _inline_smtp(monkeypatch):
    monkeypatch.setenv("ARQ_INLINE", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    from app.config import get_settings
    get_settings.cache_clear()


async def test_send_email_routes_through_arq_inline_to_smtplib():
    fake_smtp = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_smtp
    with patch("smtplib.SMTP", return_value=fake_ctx) as ctor:
        from app.services.email import send_email
        await send_email(to="a@b.c", subject="hi", body="hello")
    ctor.assert_called_once_with("smtp.example.test", 587)
    fake_smtp.send_message.assert_called_once()


async def test_send_email_dev_mode_no_smtp_call(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP") as ctor:
        from app.services.email import send_email
        await send_email(to="a@b.c", subject="hi", body="hello")
    ctor.assert_not_called()


async def test_arq_send_email_failure_raises_for_retry(monkeypatch):
    """Task body must re-raise so ARQ records the failure for retry."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.workers.tasks import send_email_task
    with patch("smtplib.SMTP", side_effect=ConnectionError("boom")):
        with pytest.raises(ConnectionError):
            await send_email_task({}, to="a@b.c", subject="hi", body="b")
