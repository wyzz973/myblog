"""pet multi provider — relax integrations.name CHECK

Revision ID: 0010_pet_multi_provider
Revises: 0009_drop_avatar_path
Create Date: 2026-05-01

The pet uses an LLM gateway that supports multiple Chinese providers.
This migration relaxes ``ck_integrations_name`` so admins can store
zhipu / qwen / doubao API keys alongside the existing github + anthropic
entries. Downgrade drops any rows for the new providers (otherwise the
restored constraint would reject them).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010_pet_multi_provider"
down_revision: str | None = "0009_drop_avatar_path"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

NEW = "name IN ('github','anthropic','zhipu','qwen','doubao')"
OLD = "name IN ('github','anthropic')"


def upgrade() -> None:
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", NEW)


def downgrade() -> None:
    # Drop any rows for new providers before restoring the old constraint —
    # otherwise the recreate would fail on existing zhipu/qwen/doubao rows.
    op.execute(
        "DELETE FROM integrations WHERE name IN ('zhipu','qwen','doubao')"
    )
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", OLD)
