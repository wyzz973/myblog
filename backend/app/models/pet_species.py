from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PetSpecies(Base):
    """Catalog of pet species shown by AsciiPet on the public site.

    Currently the JS source-of-truth (src/components/pet/species.js)
    holds 28 hardcoded entries; this table will eventually replace it
    so adding / tweaking a species doesn't need a redeploy. Task 21a
    only creates the schema — backfill, admin UI, and public read
    endpoint are tracked separately as 21b / 21c / 21d.
    """

    __tablename__ = "pet_species"
    __table_args__ = (
        CheckConstraint(
            "rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')",
            name="ck_pet_species_rarity",
        ),
        Index("ix_pet_species_visible_sort", "visible", "sort_order"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rarity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="common", server_default="common"
    )
    color: Mapped[str] = mapped_column(
        String(16), nullable=False, default="#888", server_default="#888"
    )
    trait_zh: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    personality_zh: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    description_zh: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    frames: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    behavior: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
