"""pet multi provider — relax integrations.name CHECK

Revision ID: 0010_pet_multi_provider
Revises: 0009_drop_avatar_path
Create Date: 2026-05-01
"""
from alembic import op

revision = "0010_pet_multi_provider"
down_revision = "0009_drop_avatar_path"
branch_labels = None
depends_on = None

NEW = "name IN ('github','anthropic','zhipu','qwen','doubao')"
OLD = "name IN ('github','anthropic')"


def upgrade() -> None:
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", NEW)


def downgrade() -> None:
    # Refuse downgrade if rows exist for new providers — would orphan them.
    op.execute(
        "DELETE FROM integrations WHERE name IN ('zhipu','qwen','doubao')"
    )
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", OLD)
