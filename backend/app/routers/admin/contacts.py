from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Contact
from app.services.event_log import write_event

router = APIRouter()


class ContactIn(BaseModel):
    label: str
    value: str
    href: str
    visible: bool = True
    sort_order: int = 0


class ContactOut(ContactIn):
    id: int
    model_config = {"from_attributes": True}


@router.get("/contacts", response_model=list[ContactOut])
async def list_(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    rows = (
        await s.execute(select(Contact).order_by(Contact.sort_order))
    ).scalars().all()
    return [ContactOut.model_validate(r) for r in rows]


@router.post("/contacts", response_model=ContactOut, status_code=201, dependencies=[Depends(require_scope("write"))])
async def create(
    payload: ContactIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    c = Contact(**payload.model_dump())
    s.add(c)
    await s.flush()
    await write_event(
        s, type="contact.created", actor=admin.email, target=str(c.id)
    )
    return ContactOut.model_validate(c)


@router.put("/contacts/order", status_code=204, dependencies=[Depends(require_scope("write"))])
async def reorder(
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    ids = payload.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise HTTPException(status_code=422, detail="ids: list[int] required")
    for sort_order, cid in enumerate(ids):
        c = (
            await s.execute(select(Contact).where(Contact.id == cid))
        ).scalar_one_or_none()
        if c is None:
            raise HTTPException(
                status_code=422, detail=f"contact id {cid} not found"
            )
        c.sort_order = sort_order
    await write_event(s, type="contact.reordered", actor=admin.email)


@router.patch("/contacts/{cid}", response_model=ContactOut, dependencies=[Depends(require_scope("write"))])
async def patch(
    cid: int,
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    c = (
        await s.execute(select(Contact).where(Contact.id == cid))
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("label", "value", "href", "visible", "sort_order"):
        if k in payload:
            setattr(c, k, payload[k])
    await write_event(
        s, type="contact.updated", actor=admin.email, target=str(cid)
    )
    return ContactOut.model_validate(c)


@router.delete("/contacts/{cid}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete(
    cid: int,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    c = (
        await s.execute(select(Contact).where(Contact.id == cid))
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(c)
    await write_event(
        s, type="contact.deleted", actor=admin.email, target=str(cid)
    )
