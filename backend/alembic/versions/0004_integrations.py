"""integrations

Revision ID: 0004_integrations
Revises: 0003_interactions

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_integrations"
down_revision: str | None = "0003_interactions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("extra_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("name IN ('github','anthropic')", name="ck_integrations_name"),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "now_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("listening", sa.String(length=256), nullable=True),
        sa.Column("reading", sa.String(length=256), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_now_entries_one_current",
        "now_entries",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("ix_now_entries_one_current", table_name="now_entries")
    op.drop_table("now_entries")
    op.drop_table("integrations")
