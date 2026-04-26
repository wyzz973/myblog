"""auth phase3

Revision ID: 0002_auth_phase3
Revises: 0001_initial

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_auth_phase3"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "magic_links",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_magic_links_expires_at", "magic_links", ["expires_at"])

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('read', 'write')", name="ck_api_tokens_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_api_tokens_active",
        "api_tokens",
        ["revoked_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "tfa_recovery_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code_hash"),
    )
    op.create_index("ix_tfa_recovery_codes_account_id", "tfa_recovery_codes", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_tfa_recovery_codes_account_id", table_name="tfa_recovery_codes")
    op.drop_table("tfa_recovery_codes")
    op.drop_index("ix_api_tokens_active", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_magic_links_expires_at", table_name="magic_links")
    op.drop_table("magic_links")
