"""api_tokens: add usage_count

Revision ID: 0014_api_token_usage_count
Revises: 0013_pet_smart_interaction

Adds an integer counter that gets incremented on every successful
api-token authenticated request (alongside the existing last_used_at
touch). Defaults to 0 for existing rows.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_api_token_usage_count"
down_revision: str | None = "0013_pet_smart_interaction"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_tokens",
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("api_tokens", "usage_count")
