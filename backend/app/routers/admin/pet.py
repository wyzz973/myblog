from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, SiteMeta
from app.schemas.pet import PetConfig, PetModeTemplates, PetPersonas

router = APIRouter()

ResetSection = Literal["personas", "templates", "both"]


@router.get("/pet", response_model=PetConfig)
async def get_pet(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
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


@router.get("/pet/defaults")
async def get_pet_defaults(
    _admin: Account = Depends(current_admin),
) -> dict:
    """Return schema defaults for personas + mode_templates so the frontend
    'Reset to defaults' button doesn't have to keep its own copy."""
    defaults = PetConfig()
    return {
        "personas": defaults.personas.model_dump(),
        "mode_templates": defaults.mode_templates.model_dump(),
    }


@router.post(
    "/pet/reset",
    response_model=PetConfig,
    dependencies=[Depends(require_scope("write"))],
)
async def reset_pet_section(
    section: ResetSection = Query(...),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    """Reset personas / templates / both back to schema defaults.
    Other PetConfig fields are preserved."""
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    cur = PetConfig(**{**PetConfig().model_dump(), **(site.pet_config or {})})
    payload = cur.model_dump()
    if section in ("personas", "both"):
        payload["personas"] = PetPersonas().model_dump()
    if section in ("templates", "both"):
        payload["mode_templates"] = PetModeTemplates().model_dump()
    new = PetConfig(**payload)
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=new.model_dump())
    )
    await s.commit()
    return new
