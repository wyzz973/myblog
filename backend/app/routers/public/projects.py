from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project
from app.schemas.project import ProjectPayload

router = APIRouter()


@router.get("/projects", response_model=list[ProjectPayload])
async def list_projects(s: AsyncSession = Depends(get_session)) -> list[ProjectPayload]:
    rows = (
        await s.execute(
            select(Project).where(Project.visible.is_(True)).order_by(Project.sort_order)
        )
    ).scalars().all()
    return [
        ProjectPayload(
            name=r.name, desc=r.description, lang=r.lang, stars=r.stars, status=r.status
        )
        for r in rows
    ]
