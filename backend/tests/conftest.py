"""Shared pytest fixtures for the backend test suite."""
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.logging_config import configure_logging
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _configure_logging(monkeypatch_session) -> None:
    configure_logging()


@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    mp.setenv("ARQ_INLINE", "true")
    yield mp
    mp.undo()


@pytest.fixture
async def redis():
    """In-memory fakeredis client. Test-isolated: cleared at fixture teardown."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def client(redis) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient with the app's get_redis dependency overridden to fakeredis."""
    from app import db as _db
    from app.redis import get_redis

    app = create_app()

    async def _fake_get_redis():
        yield redis

    app.dependency_overrides[get_redis] = _fake_get_redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        await _db.engine.dispose()
