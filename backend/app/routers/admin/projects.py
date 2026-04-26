from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Project
from app.services.event_log import write_event

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    description: str
    lang: str
    stars: int = 0
    status: str = "active"
    sort_order: int = 0
    visible: bool = True


class ProjectOut(ProjectIn):
    model_config = {"from_attributes": True}


@router.get("/projects", response_model=list[ProjectOut])
async def list_(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    rows = (
        await s.execute(select(Project).order_by(Project.sort_order))
    ).scalars().all()
    return [ProjectOut.model_validate(r) for r in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create(
    payload: ProjectIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    if (
        await s.execute(select(Project).where(Project.name == payload.name))
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="name taken")
    p = Project(**payload.model_dump())
    s.add(p)
    await write_event(
        s, type="project.created", actor=admin.email, target=payload.name
    )
    await s.flush()
    return ProjectOut.model_validate(p)


@router.put("/projects/order", status_code=204)
async def reorder(
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    names = payload.get("ids")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise HTTPException(
            status_code=422, detail="ids: list[str] (project names) required"
        )
    for sort_order, name in enumerate(names):
        p = (
            await s.execute(select(Project).where(Project.name == name))
        ).scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=422, detail=f"project {name} not found")
        p.sort_order = sort_order
    await write_event(s, type="project.reordered", actor=admin.email)


@router.patch("/projects/{name}", response_model=ProjectOut)
async def patch(
    name: str,
    payload: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    p = (
        await s.execute(select(Project).where(Project.name == name))
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("description", "lang", "stars", "status", "sort_order", "visible"):
        if k in payload:
            setattr(p, k, payload[k])
    await write_event(s, type="project.updated", actor=admin.email, target=name)
    return ProjectOut.model_validate(p)


@router.delete("/projects/{name}", status_code=204)
async def delete(
    name: str,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    p = (
        await s.execute(select(Project).where(Project.name == name))
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(p)
    await write_event(s, type="project.deleted", actor=admin.email, target=name)
