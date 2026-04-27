from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account
from app.schemas.now import NowCreateRequest, NowEntryItem, NowPatchRequest
from app.services import now as now_svc
from app.services.event_log import write_event

router = APIRouter()


def _to_item(row) -> NowEntryItem:
    return NowEntryItem(
        id=row.id, body_md=row.body_md, listening=row.listening,
        reading=row.reading, is_current=row.is_current, created_at=row.created_at,
    )


@router.get("/now", response_model=list[NowEntryItem])
async def list_now(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[NowEntryItem]:
    return [_to_item(r) for r in await now_svc.list_all(s)]


@router.post("/now", response_model=NowEntryItem, dependencies=[Depends(require_scope("write"))])
async def create_now(
    req: NowCreateRequest,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> NowEntryItem:
    row = await now_svc.create(
        s, body_md=req.body_md, listening=req.listening,
        reading=req.reading, is_current=req.is_current,
    )
    await write_event(
        s, type="now.created", actor=_admin.email,
        target=str(row.id), meta={"is_current": row.is_current},
    )
    await s.commit()
    return _to_item(row)


@router.patch("/now/{entry_id}", response_model=NowEntryItem,
              dependencies=[Depends(require_scope("write"))])
async def patch_now(
    entry_id: int,
    req: NowPatchRequest,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> NowEntryItem:
    row = await now_svc.patch(
        s, entry_id=entry_id,
        body_md=req.body_md, listening=req.listening,
        reading=req.reading, is_current=req.is_current,
    )
    if row is None:
        raise HTTPException(404, "now entry not found")
    fields = list(req.model_dump(exclude_none=True).keys())
    await write_event(
        s, type="now.updated", actor=_admin.email,
        target=str(entry_id), meta={"fields_changed": fields},
    )
    await s.commit()
    return _to_item(row)


@router.delete("/now/{entry_id}", status_code=204,
               dependencies=[Depends(require_scope("write"))])
async def delete_now(
    entry_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    ok = await now_svc.delete_one(s, entry_id=entry_id)
    if not ok:
        raise HTTPException(404, "now entry not found")
    await write_event(s, type="now.deleted", actor=_admin.email, target=str(entry_id))
    await s.commit()
    return Response(status_code=204)
