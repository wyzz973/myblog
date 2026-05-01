"""pet add deepseek provider

Revision ID: 0011_pet_add_deepseek
Revises: 0010_pet_multi_provider
Create Date: 2026-05-01

Adds 'deepseek' to the integrations.name CHECK constraint.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0011_pet_add_deepseek"
down_revision: str | None = "0010_pet_multi_provider"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

NEW = "name IN ('github','anthropic','zhipu','qwen','doubao','deepseek')"
OLD = "name IN ('github','anthropic','zhipu','qwen','doubao')"


def upgrade() -> None:
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", NEW)


def downgrade() -> None:
    op.execute("DELETE FROM integrations WHERE name = 'deepseek'")
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", OLD)
