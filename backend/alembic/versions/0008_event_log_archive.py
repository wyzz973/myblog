"""event_log_archive

Revision ID: 0008_event_log_archive
Revises: 0007_danger

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_event_log_archive"
down_revision: str | None = "0007_danger"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_log_archive",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column(
            "meta",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_log_archive_created_at",
        "event_log_archive",
        ["created_at"],
    )
    op.create_index(
        "ix_event_log_archive_type_created",
        "event_log_archive",
        ["type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_log_archive_type_created", table_name="event_log_archive")
    op.drop_index("ix_event_log_archive_created_at", table_name="event_log_archive")
    op.drop_table("event_log_archive")
