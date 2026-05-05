"""Pydantic schemas for the pet species catalogue (Task 21a).

Lives in its own module so the Pet (PetConfig) schemas keep their
existing _Strict shape without growing a sub-section. The router that
consumes these schemas lands in 21c.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Rarity = Literal["common", "uncommon", "rare", "epic", "legendary"]

# Slug pattern matches what AsciiPet expects today: lowercase ASCII +
# digits + dashes, 1..32 chars, must start with a letter.
SPECIES_ID_PATTERN = r"^[a-z][a-z0-9-]{0,31}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PetSpeciesBase(_Strict):
    name: str = Field(min_length=1, max_length=64)
    rarity: Rarity = "common"
    color: str = Field(default="#888", min_length=4, max_length=16)
    trait_zh: str = Field(default="", max_length=512)
    personality_zh: str = Field(default="", max_length=512)
    description_zh: str = Field(default="", max_length=2048)
    # Frames: list of multi-line strings — each frame is one ASCII pose.
    # We keep the validation loose at the schema level (just a list of
    # strings) since AsciiPet does layout validation client-side.
    frames: list[str] = Field(default_factory=list, max_length=12)
    behavior: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
    visible: bool = True
    sort_order: int = Field(default=0, ge=0)


class PetSpeciesIn(PetSpeciesBase):
    """Body for POST /pet/species — caller provides the id."""
    id: str = Field(pattern=SPECIES_ID_PATTERN, min_length=1, max_length=64)


class PetSpeciesPatch(_Strict):
    """Body for PATCH /pet/species/{id}. Every field optional."""
    name: str | None = Field(default=None, min_length=1, max_length=64)
    rarity: Rarity | None = None
    color: str | None = Field(default=None, min_length=4, max_length=16)
    trait_zh: str | None = Field(default=None, max_length=512)
    personality_zh: str | None = Field(default=None, max_length=512)
    description_zh: str | None = Field(default=None, max_length=2048)
    frames: list[str] | None = Field(default=None, max_length=12)
    behavior: dict[str, Any] | None = None
    stats: dict[str, Any] | None = None
    visible: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class PetSpeciesOut(PetSpeciesBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")
