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


@pytest.fixture(scope="session", autouse=True)
def _register_arq_tasks() -> None:
    """Register all ARQ tasks in the inline-mode registry for tests."""
    from app.workers import queue as q
    from app.workers import tasks as t
    q.register("send_email_task", t.send_email_task)
    q.register("analytics_rollup", t.analytics_rollup)
    q.register("build_export_task", t.build_export_task)
    q.register("check_pending_site_deletion", t.check_pending_site_deletion)
    q.register("prune_old_exports", t.prune_old_exports)


@pytest.fixture
async def reseed_after():
    """Use in tests that wipe site content. Restores CLI bootstrap seed
    (tags, site_meta, projects) at teardown so alphabetically-later tests
    that depend on a seeded Tag row still pass."""
    yield
    from app.cli import _seed_bootstrap
    await _seed_bootstrap()


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
