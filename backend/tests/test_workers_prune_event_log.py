from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import EventLog, EventLogArchive
from app.workers.tasks import prune_event_log


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose asyncpg pool between tests to avoid Future-attached-to-different-loop."""
    from app import db as _db
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seeded_events():
    async with AsyncSessionLocal() as s:
        await s.execute(delete(EventLog).where(EventLog.type.like("p5.test.%")))
        await s.execute(
            delete(EventLogArchive).where(EventLogArchive.type.like("p5.test.%"))
        )
        s.add_all([
            EventLog(type="p5.test.young", actor="t", target="x", meta={},
                     created_at=datetime.now(UTC) - timedelta(days=30)),
            EventLog(type="p5.test.old", actor="t", target="y", meta={},
                     created_at=datetime.now(UTC) - timedelta(days=100)),
            EventLog(type="p5.test.ancient", actor="t", target="z", meta={},
                     created_at=datetime.now(UTC) - timedelta(days=400)),
        ])
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(EventLog).where(EventLog.type.like("p5.test.%")))
        await s.execute(
            delete(EventLogArchive).where(EventLogArchive.type.like("p5.test.%"))
        )
        await s.commit()


async def test_prune_keeps_under_90_days(seeded_events):
    result = await prune_event_log({})
    # Two of three rows older than 90d are archived (out of the live table).
    assert result["archived"] == 2

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(EventLog).where(EventLog.type.like("p5.test.%"))
        )).scalars().all()
        types = {r.type for r in rows}
        assert types == {"p5.test.young"}
