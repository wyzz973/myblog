"""Danger zone service: password verification, export job lifecycle,
delete scheduling, status."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, ExportJob, SiteMeta
from app.schemas.danger import DangerStatusResponse
from app.services.auth import verify_password
from app.workers import queue as q


class DangerError(Exception):
    """Raised when a danger zone precondition fails (wrong password, already
    scheduled, etc.). Routers catch and translate to HTTP."""


async def verify_password_or_raise(
    s: AsyncSession, *, admin: Account, password: str
) -> None:
    if not verify_password(admin.password_hash, password):
        raise DangerError("invalid credentials")


async def request_export(s: AsyncSession, *, admin: Account) -> ExportJob:
    job = ExportJob(
        id=uuid.uuid4().hex,
        status="pending",
        requested_by=admin.email,
        created_at=datetime.now(UTC),
    )
    s.add(job)
    await s.flush()
    await s.refresh(job)
    await q.enqueue("build_export_task", job_id=job.id)
    return job


async def get_export(s: AsyncSession, *, job_id: str) -> ExportJob | None:
    return (
        await s.execute(select(ExportJob).where(ExportJob.id == job_id))
    ).scalar_one_or_none()


async def list_exports(
    s: AsyncSession, *, limit: int = 20
) -> list[ExportJob]:
    return list(
        (
            await s.execute(
                select(ExportJob).order_by(ExportJob.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def schedule_site_deletion(
    s: AsyncSession, *, days: int = 7
) -> datetime:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if sm.pending_delete_at is not None:
        raise DangerError("delete already scheduled")
    when = datetime.now(UTC) + timedelta(days=days)
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=when)
    )
    await s.flush()
    return when


async def cancel_site_deletion(s: AsyncSession) -> None:
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=None)
    )
    await s.flush()


async def get_danger_status(s: AsyncSession) -> DangerStatusResponse:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if sm.pending_delete_at is None:
        return DangerStatusResponse(pending_delete_at=None, days_remaining=None)
    remaining = sm.pending_delete_at - datetime.now(UTC)
    return DangerStatusResponse(
        pending_delete_at=sm.pending_delete_at,
        days_remaining=max(0, remaining.days),
    )
