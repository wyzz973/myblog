from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Contact
from app.schemas.contact import ContactPayload

router = APIRouter()


@router.get("/contacts", response_model=list[ContactPayload])
async def list_contacts(s: AsyncSession = Depends(get_session)) -> list[ContactPayload]:
    rows = (
        await s.execute(
            select(Contact).where(Contact.visible.is_(True)).order_by(Contact.sort_order)
        )
    ).scalars().all()
    return [ContactPayload.model_validate(r) for r in rows]
