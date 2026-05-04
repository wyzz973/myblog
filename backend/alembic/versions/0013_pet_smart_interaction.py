"""pet smart interaction memory and usage

Revision ID: 0013_pet_smart_interaction
Revises: 0012_add_pet_message
Create Date: 2026-05-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_pet_smart_interaction"
down_revision: str | None = "0012_add_pet_message"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pet_message", sa.Column("message", sa.Text(), nullable=True))
    op.add_column("pet_message", sa.Column("intent", sa.String(48), nullable=True))
    op.add_column(
        "pet_message",
        sa.Column("client_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "pet_message",
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pet_message",
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pet_message",
        sa.Column("estimated_total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pet_message",
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pet_message",
        sa.Column("fallback_level", sa.String(16), nullable=False, server_default="none"),
    )

    op.create_table(
        "pet_visitor_profile",
        sa.Column("visitor_hash", sa.String(16), primary_key=True),
        sa.Column("species", sa.String(32), nullable=False),
        sa.Column("locale", sa.String(32), nullable=True),
        sa.Column("preferred_language", sa.String(16), nullable=True),
        sa.Column(
            "interest_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recent_post_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("style_summary", sa.Text(), nullable=True),
        sa.Column("memory_summary", sa.Text(), nullable=True),
        sa.Column("proactive_muted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "extra_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "pet_usage_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("visitor_hash", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fallback_level", sa.String(16), nullable=False, server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_pet_usage_event_created_at", "pet_usage_event", ["created_at"])
    op.create_index(
        "ix_pet_usage_event_visitor_created",
        "pet_usage_event",
        ["visitor_hash", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pet_usage_event_visitor_created", table_name="pet_usage_event")
    op.drop_index("ix_pet_usage_event_created_at", table_name="pet_usage_event")
    op.drop_table("pet_usage_event")
    op.drop_table("pet_visitor_profile")
    op.drop_column("pet_message", "fallback_level")
    op.drop_column("pet_message", "cache_hit")
    op.drop_column("pet_message", "estimated_total_tokens")
    op.drop_column("pet_message", "estimated_output_tokens")
    op.drop_column("pet_message", "estimated_input_tokens")
    op.drop_column("pet_message", "client_context")
    op.drop_column("pet_message", "intent")
    op.drop_column("pet_message", "message")
