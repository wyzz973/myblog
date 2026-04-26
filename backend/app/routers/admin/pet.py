from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, SiteMeta
from app.schemas.pet import PetConfig

router = APIRouter()


@router.get("/pet", response_model=PetConfig)
async def get_pet(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    # Fill missing fields with defaults
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.put("/pet", response_model=PetConfig, dependencies=[Depends(require_scope("write"))])
async def put_pet(
    req: PetConfig,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=req.model_dump())
    )
    await s.commit()
    return req
