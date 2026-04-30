"""drop site_meta.avatar_path

Revision ID: 0009_drop_avatar_path
Revises: 0008_event_log_archive

The legacy ``avatar_path`` free-form column is superseded by ``avatar_id``,
the FK to ``media`` introduced in 0005. P7-A2 made site responses derive
``avatar_path`` from ``url_for(media.storage_path)`` at read time, leaving
the column unwritten. This migration removes it.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_drop_avatar_path"
down_revision: str | None = "0008_event_log_archive"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("site_meta", "avatar_path")


def downgrade() -> None:
    op.add_column(
        "site_meta",
        sa.Column("avatar_path", sa.String(length=256), nullable=True),
    )
