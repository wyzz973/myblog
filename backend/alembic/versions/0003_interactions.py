"""interactions

Revision ID: 0003_interactions
Revises: 0002_auth_phase3

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_interactions"
down_revision: str | None = "0002_auth_phase3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "like_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "ip_hash", "day", name="uq_like_events_post_ip_day"),
    )
    op.create_index("ix_like_events_post_id", "like_events", ["post_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("who", sa.String(length=64), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("actor", sa.String(length=8), nullable=False, server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('pending','approved','spam')", name="ck_comments_status"),
        sa.CheckConstraint("actor IN ('public','admin')", name="ck_comments_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_post_status", "comments", ["post_id", "status"])
    op.create_index("ix_comments_status_created", "comments", ["status", sa.text("created_at DESC")])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_status_created", table_name="comments")
    op.drop_index("ix_comments_post_status", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_like_events_post_id", table_name="like_events")
    op.drop_table("like_events")
