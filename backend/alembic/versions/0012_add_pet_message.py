"""add pet_message table

Revision ID: 0012_add_pet_message
Revises: 0011_pet_add_deepseek
Create Date: 2026-05-02

Companion to Redis pet:ctx:* short-term context: the durable archive
of every pet summon turn for admin browsing.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_add_pet_message"
down_revision: str | None = "0011_pet_add_deepseek"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_message",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("visitor_hash", sa.String(16), nullable=False),
        sa.Column("species", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("post_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("tag_slug", sa.String(40), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("selection", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "prior_turns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pet_message_visitor_hash_created",
        "pet_message",
        ["visitor_hash", "created_at"],
    )
    op.create_index("ix_pet_message_created_at", "pet_message", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_pet_message_created_at", table_name="pet_message")
    op.drop_index("ix_pet_message_visitor_hash_created", table_name="pet_message")
    op.drop_table("pet_message")
