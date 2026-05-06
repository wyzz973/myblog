"""pending_email_change table — magic-link email rotation (Task 28c).

Stores a one-shot token tied to a target new email. Confirming the token
rotates account.email; until then the account stays on the old address.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0018_pending_email_change"
down_revision: str | None = "0017_api_token_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_email_change",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("new_email", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pending_email_change_account",
        "pending_email_change",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_email_change_account", table_name="pending_email_change")
    op.drop_table("pending_email_change")
