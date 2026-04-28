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


async def test_check_pending_no_schedule_is_noop(cleanup_jobs):
    from app.workers.tasks.danger import check_pending_site_deletion
    res = await check_pending_site_deletion({})
    assert res == {"checked": 1, "fired": 0}


async def test_check_pending_in_past_fires_wipe(cleanup_jobs, tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)
    from app.workers.tasks.danger import check_pending_site_deletion

    past = datetime.now(UTC) - timedelta(hours=1)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=past))
        await s.commit()

    res = await check_pending_site_deletion({})
    assert res == {"checked": 1, "fired": 1}

    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is None


async def test_prune_old_exports_deletes_aged_files_and_rows(cleanup_jobs, tmp_path, monkeypatch):
    """Seed an old zip + a recent zip + corresponding rows; verify pruning."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    old_zip = exports_dir / "old.zip"
    old_zip.write_bytes(b"PK\x03\x04 stub")
    # Set mtime to 8 days ago.
    import os
    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).timestamp()
    os.utime(old_zip, (eight_days_ago, eight_days_ago))

    new_zip = exports_dir / "new.zip"
    new_zip.write_bytes(b"PK\x03\x04 stub")  # mtime ≈ now

    async with AsyncSessionLocal() as s2:
        s2.add(ExportJob(id="old", status="done", requested_by="x@x.com",
                         created_at=datetime.now(UTC) - timedelta(days=8)))
        s2.add(ExportJob(id="new", status="done", requested_by="x@x.com",
                         created_at=datetime.now(UTC)))
        await s2.commit()

    from app.workers.tasks.danger import prune_old_exports
    res = await prune_old_exports({})
    assert res["files_deleted"] >= 1
    assert res["rows_deleted"] >= 1

    assert not old_zip.exists()
    assert new_zip.exists()

    async with AsyncSessionLocal() as s3:
        rows = (await s3.execute(select(ExportJob))).scalars().all()
    assert {r.id for r in rows} == {"new"}


async def test_prune_old_exports_no_op_when_nothing_old(cleanup_jobs, tmp_path, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    from app.workers.tasks.danger import prune_old_exports
    res = await prune_old_exports({})
    assert res == {"files_deleted": 0, "rows_deleted": 0}
