"""Shared pytest fixtures for the backend test suite.

Task 21 in the plan introduces a httpx ASGI client fixture; this file is
created early so logging is configured for every test session (otherwise
`app.main:lifespan` is never driven under `httpx.ASGITransport`).
"""
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.logging_config import configure_logging
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _configure_logging() -> None:
    configure_logging()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient bound to a fresh ASGI app instance per test.

    Phase 1 runs tests against the dev DB to keep complexity low; Phase 4
    introduces `pytest-postgresql`-driven schema isolation as the suite grows.
    """
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
