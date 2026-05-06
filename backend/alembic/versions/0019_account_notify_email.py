"""account.notify_comments + account.notify_email override (Task 43).

Lets the owner disable comment notification emails or override the
target address from the admin UI without touching ``.env``. The previous
fallback chain (settings → account.email) keeps working when both new
columns are at defaults.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0019_account_notify_email"
down_revision: str | None = "0018_pending_email_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "notify_comments", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("notify_email", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "notify_email")
    op.drop_column("accounts", "notify_comments")
