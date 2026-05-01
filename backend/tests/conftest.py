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
    (site_meta singleton + the 'devtools' fixture tag) at teardown so
    alphabetically-later tests that depend on a seeded Tag row still pass."""
    yield
    from app.cli import _seed_bootstrap
    await _seed_bootstrap()
    await _ensure_devtools_tag_exists()


async def _ensure_devtools_tag_exists() -> None:
    """The 'devtools' tag is referenced by post fixtures (GOOD_MD, export
    builder seeds). It used to come from cli.DEFAULT_TAGS but the project
    no longer ships seeded tags, so tests provision it directly."""
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models import Tag
    async with AsyncSessionLocal() as s:
        existing = (
            await s.execute(select(Tag).where(Tag.slug == "devtools"))
        ).scalar_one_or_none()
        if existing is None:
            s.add(Tag(slug="devtools", name="devtools", color="#7dd3a4", sort_order=0))
            await s.commit()




@pytest.fixture
async def fake_post_id():
    """Create a minimal Post row for pet context tests. Reuses 'devtools' tag."""
    from datetime import date

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import engine
    from app.models import Post, Tag

    pid = "pet-test"
    async with AsyncSession(engine) as s:
        # Look up the devtools tag (created by _ensure_devtools_tag_exists in client fixture)
        tag = (await s.execute(select(Tag).where(Tag.slug == "devtools"))).scalar_one_or_none()
        if tag is None:
            tag = Tag(slug="devtools", name="devtools", color="#7dd3a4", sort_order=0)
            s.add(tag)
            await s.flush()
        existing = await s.get(Post, pid)
        if existing is None:
            s.add(Post(
                id=pid,
                n="001",
                title="Pet Test",
                tag_id=tag.id,
                date=date(2024, 1, 1),
                status="published",
                summary="A short summary.",
                body_md="# hi",
            ))
            await s.commit()
    yield pid


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

    # Most async tests live behind this fixture and reference 'devtools' in
    # post frontmatter. Ensure the tag exists before each test (idempotent).
    await _ensure_devtools_tag_exists()

    app = create_app()

    async def _fake_get_redis():
        yield redis

    app.dependency_overrides[get_redis] = _fake_get_redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        await _db.engine.dispose()
