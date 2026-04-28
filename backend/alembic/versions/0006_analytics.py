"""analytics

Revision ID: 0006_analytics
Revises: 0005_media

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_analytics"
down_revision: str | None = "0005_media"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("referrer", sa.String(length=512), nullable=True),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("post_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hit_events_created_at",
        "hit_events",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_hit_events_post_id",
        "hit_events",
        ["post_id"],
        postgresql_where=sa.text("post_id IS NOT NULL"),
    )

    op.create_table(
        "hit_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=True),
        sa.Column(
            "referrers_top",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "countries_top",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("date", "path"),
    )
    op.create_index(
        "ix_hit_daily_date",
        "hit_daily",
        [sa.text("date DESC")],
    )
    op.create_index(
        "ix_hit_daily_post_id",
        "hit_daily",
        ["post_id"],
        postgresql_where=sa.text("post_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_hit_daily_post_id", table_name="hit_daily")
    op.drop_index("ix_hit_daily_date", table_name="hit_daily")
    op.drop_table("hit_daily")
    op.drop_index("ix_hit_events_post_id", table_name="hit_events")
    op.drop_index("ix_hit_events_created_at", table_name="hit_events")
    op.drop_table("hit_events")
