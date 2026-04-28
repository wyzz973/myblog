"""ARQ danger tasks unit tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import ExportJob, SiteMeta
from app.workers.tasks.danger import build_export_task


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_jobs():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(ExportJob))
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=None))
        await s.commit()


@pytest.fixture
async def export_dir(tmp_path, monkeypatch):
    from app.services import export_builder
    monkeypatch.setattr(export_builder, "_exports_dir", lambda: tmp_path)
    return tmp_path


async def test_build_export_task_happy_path(cleanup_jobs, export_dir):
    job_id = "btest-ok"
    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id=job_id, status="pending", requested_by="x@x.com",
            created_at=datetime.now(UTC),
        ))
        await s.commit()

    res = await build_export_task({}, job_id=job_id)
    assert res["status"] == "done"
    assert res["file_size"] > 0

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ExportJob).where(ExportJob.id == job_id))).scalar_one()
    assert row.status == "done"
    assert row.file_size > 0
    assert row.completed_at is not None
    assert (export_dir / f"{job_id}.zip").exists()


async def test_build_export_task_failure_path(cleanup_jobs, export_dir, monkeypatch):
    job_id = "btest-fail"
    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id=job_id, status="pending", requested_by="x@x.com",
            created_at=datetime.now(UTC),
        ))
        await s.commit()

    from app.services import export_builder
    async def _boom(jid):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(export_builder, "build_export_zip", _boom)

    with pytest.raises(RuntimeError, match="simulated"):
        await build_export_task({}, job_id=job_id)

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ExportJob).where(ExportJob.id == job_id))).scalar_one()
    assert row.status == "failed"
    assert row.error and "simulated" in row.error
    assert row.completed_at is not None
