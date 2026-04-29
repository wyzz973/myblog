"""Coverage for the prune_event_log retention pipeline (P7 archive lane)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import EventLog, EventLogArchive
from app.workers.tasks import prune_event_log

TAG = "p7a3.archive"


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose asyncpg pool between tests."""
    from app import db as _db
    yield
    await _db.engine.dispose()


@pytest.fixture
async def clean_archive_tables():
    """Clear our test rows before & after each test."""
    async def _wipe() -> None:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(EventLog).where(EventLog.type.like(f"{TAG}.%")))
            await s.execute(
                delete(EventLogArchive).where(EventLogArchive.type.like(f"{TAG}.%"))
            )
            await s.commit()

    await _wipe()
    yield
    await _wipe()


async def test_archive_moves_old_rows_and_keeps_recent(clean_archive_tables):
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        s.add_all(
            [
                # 3 within 90d (should stay in event_log)
                EventLog(type=f"{TAG}.young1", actor="t", target="a", meta={},
                         created_at=now - timedelta(days=1)),
                EventLog(type=f"{TAG}.young2", actor="t", target="b", meta={},
                         created_at=now - timedelta(days=30)),
                EventLog(type=f"{TAG}.young3", actor="t", target="c", meta={},
                         created_at=now - timedelta(days=89)),
                # 2 older than 90d (should move to archive)
                EventLog(type=f"{TAG}.old1", actor="t", target="d",
                         meta={"k": "v"},
                         created_at=now - timedelta(days=100)),
                EventLog(type=f"{TAG}.old2", actor="t", target="e", meta={},
                         created_at=now - timedelta(days=200)),
            ]
        )
        await s.commit()

    result = await prune_event_log({})
    assert result["archived"] == 2
    assert result["archive_pruned"] == 0

    async with AsyncSessionLocal() as s:
        live_types = {
            r.type
            for r in (
                await s.execute(
                    select(EventLog).where(EventLog.type.like(f"{TAG}.%"))
                )
            ).scalars().all()
        }
        archived_rows = (
            await s.execute(
                select(EventLogArchive).where(
                    EventLogArchive.type.like(f"{TAG}.%")
                )
            )
        ).scalars().all()

    assert live_types == {f"{TAG}.young1", f"{TAG}.young2", f"{TAG}.young3"}
    assert len(archived_rows) == 2
    archived_types = {r.type for r in archived_rows}
    assert archived_types == {f"{TAG}.old1", f"{TAG}.old2"}
    # Verify field copy fidelity
    by_type = {r.type: r for r in archived_rows}
    assert by_type[f"{TAG}.old1"].meta == {"k": "v"}
    assert by_type[f"{TAG}.old1"].target == "d"
    assert by_type[f"{TAG}.old1"].actor == "t"
    assert by_type[f"{TAG}.old1"].archived_at is not None


async def test_archive_drops_rows_older_than_one_year(clean_archive_tables):
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        # Pre-seed an archive row > 365 days old (will be dropped).
        s.add(
            EventLogArchive(
                type=f"{TAG}.ancient",
                actor="t",
                target="z",
                meta={},
                created_at=now - timedelta(days=400),
                archived_at=now - timedelta(days=310),
            )
        )
        # And an archive row only 200d old (must survive).
        s.add(
            EventLogArchive(
                type=f"{TAG}.midaged",
                actor="t",
                target="y",
                meta={},
                created_at=now - timedelta(days=200),
                archived_at=now - timedelta(days=110),
            )
        )
        await s.commit()

    result = await prune_event_log({})
    assert result["archived"] == 0
    assert result["archive_pruned"] == 1

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(EventLogArchive).where(
                    EventLogArchive.type.like(f"{TAG}.%")
                )
            )
        ).scalars().all()
    types = {r.type for r in rows}
    assert types == {f"{TAG}.midaged"}


async def test_archive_is_idempotent(clean_archive_tables):
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        s.add_all(
            [
                EventLog(type=f"{TAG}.idem1", actor="t", target="p", meta={},
                         created_at=now - timedelta(days=120)),
                EventLog(type=f"{TAG}.idem2", actor="t", target="q", meta={},
                         created_at=now - timedelta(days=150)),
            ]
        )
        await s.commit()

    first = await prune_event_log({})
    second = await prune_event_log({})

    assert first["archived"] == 2
    # Second run finds no live rows older than 90d → nothing to archive.
    assert second["archived"] == 0

    async with AsyncSessionLocal() as s:
        archived_rows = (
            await s.execute(
                select(EventLogArchive).where(
                    EventLogArchive.type.like(f"{TAG}.%")
                )
            )
        ).scalars().all()
        live_rows = (
            await s.execute(
                select(EventLog).where(EventLog.type.like(f"{TAG}.%"))
            )
        ).scalars().all()

    # Archive count is stable across re-runs (no duplicate inserts).
    assert len(archived_rows) == 2
    assert len(live_rows) == 0
