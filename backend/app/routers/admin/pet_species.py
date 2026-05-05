"""Admin CRUD for the pet species catalogue (Task 21c).

Sits next to admin/pet.py (which owns PetConfig — the per-site behavior knobs).
This router owns the catalogue itself: the rows the public GET /api/pet/species
endpoint returns and that AsciiPet renders. Owner-facing UI lands in 21d.

Design notes:
- DELETE refuses with 409 if SiteMeta.pet_config.species (the default-pet
  fallback) still points at the row. Without that gate the public site would
  serve an unknown species id and AsciiPet would render its blank fallback.
- PATCH treats absent fields as "unchanged" (PetSpeciesPatch is all-optional).
- visible=false hides a row from the public catalogue without deleting it,
  so owners can park experiments without breaking visitor cookies that may
  still carry the species id.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import asc, delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, PetSpecies, SiteMeta
from app.schemas.pet_species import PetSpeciesIn, PetSpeciesOut, PetSpeciesPatch
from app.services.event_log import write_event


router = APIRouter()


@router.get("/pet/species", response_model=list[PetSpeciesOut])
async def list_species(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[PetSpeciesOut]:
    rows = (
        await s.execute(
            select(PetSpecies).order_by(asc(PetSpecies.sort_order), asc(PetSpecies.id))
        )
    ).scalars().all()
    return [PetSpeciesOut.model_validate(r) for r in rows]


@router.post(
    "/pet/species",
    response_model=PetSpeciesOut,
    dependencies=[Depends(require_scope("write"))],
)
async def create_species(
    body: PetSpeciesIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetSpeciesOut:
    existing = (
        await s.execute(select(PetSpecies).where(PetSpecies.id == body.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"species id {body.id!r} already exists",
        )
    now = datetime.now(UTC)
    row = PetSpecies(
        id=body.id,
        name=body.name,
        rarity=body.rarity,
        color=body.color,
        trait_zh=body.trait_zh,
        personality_zh=body.personality_zh,
        description_zh=body.description_zh,
        frames=body.frames,
        behavior=body.behavior,
        stats=body.stats,
        visible=body.visible,
        sort_order=body.sort_order,
        created_at=now,
        updated_at=now,
    )
    s.add(row)
    await write_event(
        s, type="pet.species.created",
        actor=admin.email,
        meta={"id": body.id, "name": body.name, "rarity": body.rarity},
    )
    await s.commit()
    await s.refresh(row)
    return PetSpeciesOut.model_validate(row)


@router.patch(
    "/pet/species/{species_id}",
    response_model=PetSpeciesOut,
    dependencies=[Depends(require_scope("write"))],
)
async def patch_species(
    species_id: str,
    body: PetSpeciesPatch,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetSpeciesOut:
    row = (
        await s.execute(select(PetSpecies).where(PetSpecies.id == species_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="species not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return PetSpeciesOut.model_validate(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    await write_event(
        s, type="pet.species.updated",
        actor=admin.email,
        meta={"id": species_id, "fields": sorted(changes.keys())},
    )
    await s.commit()
    await s.refresh(row)
    return PetSpeciesOut.model_validate(row)


@router.delete(
    "/pet/species/{species_id}",
    status_code=204,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_species(
    species_id: str,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> None:
    row = (
        await s.execute(select(PetSpecies).where(PetSpecies.id == species_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="species not found")

    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    pet_cfg = site.pet_config or {}
    default_species = pet_cfg.get("species")
    if default_species == species_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"species {species_id!r} is the site's default pet (SiteMeta.pet_config.species). "
                "Pick a different default in 宠物配置 first, then delete."
            ),
        )

    await s.execute(sa_delete(PetSpecies).where(PetSpecies.id == species_id))
    await write_event(
        s, type="pet.species.deleted",
        actor=admin.email,
        meta={"id": species_id, "name": row.name, "rarity": row.rarity},
    )
    await s.commit()
