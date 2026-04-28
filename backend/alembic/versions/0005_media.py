"""media

Revision ID: 0005_media
Revises: 0004_integrations

Note on site_meta.avatar_path coexistence:
    site_meta has both `avatar_path` (pre-existing String(256), free-form path)
    and now `avatar_id` (FK to media). They temporarily coexist in P6a — the
    public site still serializes avatar_path. A follow-up phase (P6b or later)
    will derive avatar_path from media.url_for(avatar.storage_path) when
    avatar_id is set, then drop the avatar_path column. Until then, treat
    avatar_id as the authoritative reference and avatar_path as legacy.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_media"
down_revision: str | None = "0004_integrations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_created_at",
        "media",
        [sa.text("created_at DESC")],
    )

    op.add_column(
        "site_meta",
        sa.Column("avatar_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_site_meta_avatar_id",
        "site_meta",
        "media",
        ["avatar_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_site_meta_avatar_id", "site_meta", type_="foreignkey")
    op.drop_column("site_meta", "avatar_id")
    op.drop_index("ix_media_created_at", table_name="media")
    op.drop_table("media")
