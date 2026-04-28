"""ARQ tasks for the danger zone: export building, scheduled-deletion check,
and old-export pruning."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import ExportJob, SiteMeta
from app.services import export_builder
from app.services.event_log import write_event
from app.services.site_wiper import wipe_site_content


async def build_export_task(ctx: dict, job_id: str) -> dict:
    """Drive a single export job: pending → running → done|failed."""
    # Step 1: pending → running
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(ExportJob).where(ExportJob.id == job_id).values(status="running")
        )
        await s.commit()

    try:
        path, size = await export_builder.build_export_zip(job_id)
    except Exception as e:
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(ExportJob).where(ExportJob.id == job_id).values(
                    status="failed",
                    error=f"{type(e).__name__}: {e}",
                    completed_at=datetime.now(UTC),
                )
            )
            await write_event(
                s, type="danger.export_failed", actor="system",
                target=job_id, meta={"error": str(e)},
            )
            await s.commit()
        raise

    async with AsyncSessionLocal() as s:
        await s.execute(
            update(ExportJob).where(ExportJob.id == job_id).values(
                status="done",
                file_size=size,
                completed_at=datetime.now(UTC),
            )
        )
        await write_event(
            s, type="danger.export_completed", actor="system",
            target=job_id, meta={"file_size": size},
        )
        await s.commit()

    return {"status": "done", "job_id": job_id, "file_size": size}


async def check_pending_site_deletion(ctx: dict) -> dict:
    """Hourly cron: trigger wipe when site_meta.pending_delete_at <= NOW()."""
    fired = 0
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
        if sm.pending_delete_at is not None and sm.pending_delete_at <= datetime.now(UTC):
            stats = await wipe_site_content(s)
            await write_event(
                s, type="danger.site_wiped", actor="system",
                target=None, meta=stats,
            )
            await s.commit()
            fired = 1
    return {"checked": 1, "fired": fired}


async def prune_old_exports(ctx: dict) -> dict:
    """Daily 03:30: remove zips and rows older than 7 days."""
    cutoff = datetime.now(UTC) - timedelta(days=7)
    exports_dir = get_settings().data_dir / "exports"
    files_deleted = 0

    if exports_dir.exists():
        for f in exports_dir.iterdir():
            if f.is_file() and f.suffix == ".zip":
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    f.unlink(missing_ok=True)
                    files_deleted += 1

    async with AsyncSessionLocal() as s:
        res = await s.execute(
            delete(ExportJob).where(ExportJob.created_at < cutoff)
        )
        rows_deleted = res.rowcount or 0
        await s.commit()

    return {"files_deleted": files_deleted, "rows_deleted": rows_deleted}
