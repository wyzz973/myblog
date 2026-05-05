"""create pet_species table

Revision ID: 0015_pet_species
Revises: 0014_api_token_usage_count

The species catalogue (currently hardcoded in src/components/pet/species.js
with 28 entries) is migrated to a DB-backed table so admins can add /
tweak species without a code change. This migration only creates the
table — backfill from species.js + admin UI / public read endpoint live
in follow-up tasks (21b, 21c, 21d).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_pet_species"
down_revision: str | None = "0014_api_token_usage_count"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_species",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("rarity", sa.String(length=16), nullable=False, server_default="common"),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#888"),
        sa.Column("trait_zh", sa.Text(), nullable=False, server_default=""),
        sa.Column("personality_zh", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_zh", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "frames",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "behavior",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')",
            name="ck_pet_species_rarity",
        ),
    )
    op.create_index(
        "ix_pet_species_visible_sort", "pet_species", ["visible", "sort_order"]
    )


def downgrade() -> None:
    op.drop_index("ix_pet_species_visible_sort", table_name="pet_species")
    op.drop_table("pet_species")
