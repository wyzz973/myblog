"""Shared pytest fixtures for the backend test suite.

Task 21 in the plan introduces a httpx ASGI client fixture; this file is
created early so logging is configured for every test session (otherwise
`app.main:lifespan` is never driven under `httpx.ASGITransport`).
"""
import pytest

from app.logging_config import configure_logging


@pytest.fixture(scope="session", autouse=True)
def _configure_logging() -> None:
    configure_logging()
