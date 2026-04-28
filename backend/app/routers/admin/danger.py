"""Admin danger zone: site export + delete-site (with 7-day grace)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, ExportJob, SiteMeta
from app.redis import get_redis
from app.schemas.danger import (
    DangerStatusResponse,
    DeleteSiteRequest,
    ExportJobItem,
    ExportRequest,
    ExportRequestResponse,
    ScheduleDeleteResponse,
)
from app.services import danger as danger_svc
from app.services import export_builder, rate_limit
from app.services.client_ip import client_ip_key_part
from app.services.event_log import write_event
from app.workers import queue as q

router = APIRouter()


def _to_export_item(row: ExportJob) -> ExportJobItem:
    return ExportJobItem(
        id=row.id,
        status=row.status,
        requested_by=row.requested_by,
        file_size=row.file_size,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def _danger_rate_limit(request: Request, redis) -> None:
    ip_key = client_ip_key_part(request)
    await rate_limit.hit(redis, f"rl:danger:{ip_key}", limit=1, window_sec=3600)


@router.post(
    "/danger/export",
    response_model=ExportRequestResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def request_export_route(
    req: ExportRequest,
    request: Request,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> ExportRequestResponse:
    await _danger_rate_limit(request, redis)
    try:
        await danger_svc.verify_password_or_raise(s, admin=admin, password=req.password)
    except danger_svc.DangerError as e:
        raise HTTPException(401, "invalid credentials") from e

    # Create the row + audit event and COMMIT before enqueueing — in
    # ARQ_INLINE mode the task runs synchronously inside enqueue() and uses
    # its own DB session, so it must see a committed row.
    job = ExportJob(
        id=uuid.uuid4().hex,
        status="pending",
        requested_by=admin.email,
        created_at=datetime.now(UTC),
    )
    s.add(job)
    await s.flush()
    await write_event(
        s, type="danger.export_requested", actor=admin.email,
        target=job.id, meta={},
    )
    await s.commit()

    await q.enqueue("build_export_task", job_id=job.id)
    return ExportRequestResponse(job_id=job.id, status="pending")


@router.get(
    "/danger/export/{job_id}",
    response_model=ExportJobItem,
)
async def get_export_route(
    job_id: str,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> ExportJobItem:
    row = await danger_svc.get_export(s, job_id=job_id)
    if row is None:
        raise HTTPException(404, "export not found")
    return _to_export_item(row)


@router.get(
    "/danger/exports",
    response_model=list[ExportJobItem],
)
async def list_exports_route(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ExportJobItem]:
    rows = await danger_svc.list_exports(s, limit=20)
    return [_to_export_item(r) for r in rows]


@router.get("/danger/export/{job_id}/download")
async def download_export_route(
    job_id: str,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    row = await danger_svc.get_export(s, job_id=job_id)
    if row is None or row.status != "done":
        raise HTTPException(404, "export not ready")

    exports_dir = export_builder._exports_dir().resolve()
    candidate = (exports_dir / f"{job_id}.zip").resolve()

    # Path safety: candidate must live inside exports_dir.
    if exports_dir not in candidate.parents and candidate != exports_dir:
        raise HTTPException(404, "export not ready")
    if not candidate.exists():
        raise HTTPException(404, "export file missing on disk")

    return FileResponse(
        path=str(candidate),
        media_type="application/zip",
        filename=f"myblog-export-{job_id}.zip",
    )


@router.post(
    "/danger/delete-site",
    response_model=ScheduleDeleteResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_site_route(
    req: DeleteSiteRequest,
    request: Request,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> ScheduleDeleteResponse:
    await _danger_rate_limit(request, redis)
    try:
        await danger_svc.verify_password_or_raise(s, admin=admin, password=req.password)
    except danger_svc.DangerError as e:
        raise HTTPException(401, "invalid credentials") from e

    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if req.handle != sm.handle:
        raise HTTPException(422, "handle mismatch")

    try:
        scheduled_at = await danger_svc.schedule_site_deletion(s, days=7)
    except danger_svc.DangerError as exc:
        raise HTTPException(423, "delete already scheduled") from exc

    await write_event(
        s, type="danger.delete_scheduled", actor=admin.email,
        target=None, meta={"scheduled_at": scheduled_at.isoformat()},
    )
    await s.commit()
    return ScheduleDeleteResponse(scheduled_at=scheduled_at, days_remaining=7)


@router.post(
    "/danger/delete-site/cancel",
    status_code=204,
    dependencies=[Depends(require_scope("write"))],
)
async def cancel_delete_site_route(
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    await danger_svc.cancel_site_deletion(s)
    await write_event(
        s, type="danger.delete_canceled", actor=admin.email,
        target=None, meta={},
    )
    await s.commit()
    return Response(status_code=204)


@router.get(
    "/danger/status",
    response_model=DangerStatusResponse,
)
async def get_danger_status_route(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DangerStatusResponse:
    return await danger_svc.get_danger_status(s)
