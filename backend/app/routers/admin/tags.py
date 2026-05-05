from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Post, Tag
from app.services.event_log import write_event

router = APIRouter()


class TagIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,31}$")
    name: str
    color: str = "#7dd3a4"
    sort_order: int = 0


class TagOut(BaseModel):
    id: int
    slug: str
    name: str
    color: str
    sort_order: int
    # Post count exposed so the admin UI can warn / disable the delete button
    # for tags that still have posts attached.
    post_count: int = 0

    model_config = {"from_attributes": True}


@router.get("/tags", response_model=list[TagOut])
async def list_(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    rows = (
        await s.execute(
            select(Tag, func.count(Post.id))
            .join(Post, Post.tag_id == Tag.id, isouter=True)
            .group_by(Tag.id)
            .order_by(Tag.sort_order)
        )
    ).all()
    return [
        TagOut(
            id=t.id, slug=t.slug, name=t.name, color=t.color,
            sort_order=t.sort_order, post_count=int(c or 0),
        )
        for t, c in rows
    ]


@router.post("/tags", response_model=TagOut, status_code=201, dependencies=[Depends(require_scope("write"))])
async def create(
    payload: TagIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    if (
        await s.execute(select(Tag).where(Tag.slug == payload.slug))
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="slug taken")
    tag = Tag(**payload.model_dump())
    s.add(tag)
    await write_event(s, type="tag.created", actor=admin.email, target=payload.slug)
    await s.flush()
    return TagOut.model_validate(tag)


@router.put("/tags/order", status_code=204, dependencies=[Depends(require_scope("write"))])
async def reorder(
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    ids = payload.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise HTTPException(status_code=422, detail="ids: list[int] required")
    for sort_order, tid in enumerate(ids):
        tag = (
            await s.execute(select(Tag).where(Tag.id == tid))
        ).scalar_one_or_none()
        if tag is None:
            raise HTTPException(status_code=422, detail=f"tag id {tid} not found")
        tag.sort_order = sort_order
    await write_event(s, type="tag.reordered", actor=admin.email)


@router.patch("/tags/{tag_id}", response_model=TagOut, dependencies=[Depends(require_scope("write"))])
async def patch(
    tag_id: int,
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    tag = (
        await s.execute(select(Tag).where(Tag.id == tag_id))
    ).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("slug", "name", "color", "sort_order"):
        if k in payload:
            setattr(tag, k, payload[k])
    await write_event(s, type="tag.updated", actor=admin.email, target=tag.slug)
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete(
    tag_id: int,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    tag = (
        await s.execute(select(Tag).where(Tag.id == tag_id))
    ).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="not found")
    # Refuse delete when posts still reference the tag — the FK is RESTRICT,
    # so without this check the row stays but the response was already 204.
    in_use = (
        await s.execute(select(func.count(Post.id)).where(Post.tag_id == tag.id))
    ).scalar_one()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"tag has {in_use} post(s); reassign or delete them first",
        )
    await s.delete(tag)
    await write_event(s, type="tag.deleted", actor=admin.email, target=tag.slug)
