"""api_token_usage table — per-request log for api tokens (Task 29).

Each row is one scoped admin API call made under a token. The existing
api_tokens.usage_count is the aggregate counter; this table is the
detail trail. Index covers the per-token "show recent N" query.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0017_api_token_usage"
down_revision: str | None = "0016_pet_species_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_token_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "api_token_id",
            sa.Integer(),
            sa.ForeignKey("api_tokens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=256), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=True),
    )
    op.create_index(
        "ix_api_token_usage_token_used",
        "api_token_usage",
        ["api_token_id", sa.text("used_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_api_token_usage_token_used", table_name="api_token_usage")
    op.drop_table("api_token_usage")
