"""Task 21a: data layer for pet_species (no router yet).

Confirms the migration has applied and the model + Pydantic schemas
round-trip. Once the router lands in 21c we'll add HTTP-level tests.
"""
import pytest
from datetime import UTC, datetime
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import PetSpecies
from app.schemas.pet_species import (
    PetSpeciesIn,
    PetSpeciesOut,
    PetSpeciesPatch,
)


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_species():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(PetSpecies).where(PetSpecies.id.like("t21a-%")))
        await s.commit()


async def test_pet_species_table_exists_and_round_trips(cleanup_species):
    async with AsyncSessionLocal() as s:
        s.add(PetSpecies(
            id="t21a-duck",
            name="Duck",
            rarity="common",
            color="#7dd3a4",
            trait_zh="嘎嘎调试搭子",
            personality_zh="开朗、字面意思理解,对沉默的失败保持怀疑。",
            description_zh="一只小桌鸭,先听后嘎,只有 bug 显而易见时才出声。",
            frames=["frame1", "frame2", "frame3"],
            behavior={"proactive_level": 0.3, "idle_frequency": 90, "local_lines": []},
            stats={"patience": 78, "snark": 12},
            visible=True,
            sort_order=5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ))
        await s.commit()
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(PetSpecies).where(PetSpecies.id == "t21a-duck")
        )).scalar_one()
    assert row.name == "Duck"
    assert row.rarity == "common"
    assert row.frames == ["frame1", "frame2", "frame3"]
    assert row.behavior["proactive_level"] == 0.3
    assert row.stats["patience"] == 78
    assert row.visible is True


async def test_pet_species_rarity_check_constraint(cleanup_species):
    """The rarity CHECK should reject unknown values at the DB level."""
    from sqlalchemy.exc import IntegrityError, DBAPIError
    async with AsyncSessionLocal() as s:
        s.add(PetSpecies(
            id="t21a-bad-rarity",
            name="Bad",
            rarity="mythic",  # not in the allowed set
            color="#fff",
            frames=[],
            behavior={},
            stats={},
            visible=True,
            sort_order=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ))
        with pytest.raises((IntegrityError, DBAPIError)):
            await s.commit()


async def test_schema_in_validates_slug_pattern():
    # Valid
    p = PetSpeciesIn(
        id="duck",
        name="Duck",
        rarity="common",
        color="#7dd3a4",
        frames=["x"],
    )
    assert p.id == "duck"
    # Invalid: starts with digit / contains uppercase / too long
    from pydantic import ValidationError
    for bad in ("9bad", "Duck", "duck-" + "x" * 64, "snake_case"):
        with pytest.raises(ValidationError):
            PetSpeciesIn(id=bad, name="x")


async def test_schema_patch_all_optional():
    # Empty body must be valid (all-None means no-op patch).
    PetSpeciesPatch()
    # Partial body
    p = PetSpeciesPatch(name="Renamed", visible=False)
    dump = p.model_dump(exclude_unset=True)
    assert dump == {"name": "Renamed", "visible": False}


async def test_schema_out_round_trips_from_model(cleanup_species):
    async with AsyncSessionLocal() as s:
        s.add(PetSpecies(
            id="t21a-out",
            name="OutTest",
            rarity="rare",
            color="#a78bfa",
            trait_zh="t",
            personality_zh="p",
            description_zh="d",
            frames=["frame"],
            behavior={"x": 1},
            stats={"y": 2},
            visible=True,
            sort_order=3,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ))
        await s.commit()
        row = (await s.execute(
            select(PetSpecies).where(PetSpecies.id == "t21a-out")
        )).scalar_one()
    out = PetSpeciesOut.model_validate(row)
    assert out.id == "t21a-out"
    assert out.rarity == "rare"
    assert out.frames == ["frame"]
    assert out.created_at is not None
    assert out.updated_at is not None
