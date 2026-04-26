from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import EventLog, Post, Tag
from app.workers.tasks import publish_scheduled_posts


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the engine pool before each test so asyncpg connections are
    not carried across test-local event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seeded_posts():
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        ids = ("p5-sched-past", "p5-sched-future", "p5-already-pub")
        for pid in ids:
            await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id="p5-sched-past", n="800", title="past", tag_id=tag.id,
            date=date(2026, 1, 1), lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="scheduled",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.execute(insert(Post).values(
            id="p5-sched-future", n="801", title="future", tag_id=tag.id,
            date=date(2026, 1, 1), lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="scheduled",
            scheduled_at=datetime.now(UTC) + timedelta(hours=1),
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.execute(insert(Post).values(
            id="p5-already-pub", n="802", title="published", tag_id=tag.id,
            date=date(2026, 1, 1), lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        for pid in ids:
            await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(
            delete(EventLog).where(EventLog.target.in_(["p5-sched-past", "p5-sched-future"]))
        )
        await s.commit()


async def test_publish_scheduled_flips_only_past_due(seeded_posts):
    result = await publish_scheduled_posts({})
    assert result["count"] == 1

    async with AsyncSessionLocal() as s:
        past = (await s.execute(
            select(Post).where(Post.id == "p5-sched-past")
        )).scalar_one()
        future = (await s.execute(
            select(Post).where(Post.id == "p5-sched-future")
        )).scalar_one()
        already = (await s.execute(
            select(Post).where(Post.id == "p5-already-pub")
        )).scalar_one()
        assert past.status == "published"
        assert future.status == "scheduled"
        assert already.status == "published"


async def test_publish_scheduled_writes_event_log(seeded_posts):
    await publish_scheduled_posts({})
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(EventLog).where(
                EventLog.type == "post.published",
                EventLog.target == "p5-sched-past",
            )
        )).scalars().all()
        assert len(rows) >= 1
        assert rows[0].actor == "worker"
