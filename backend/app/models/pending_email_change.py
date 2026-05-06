from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PendingEmailChange(Base):
    """Pending email-rotation request awaiting magic-link confirmation (Task 28c).

    Caller (POST /account/email/request) verifies the current password and
    inserts a row with a hashed one-shot token. The link in the email points
    at /admin/account/email-confirm?token=... which calls /confirm and
    triggers the rotation.

    Single-use guarantee comes from the same `WHERE consumed_at IS NULL`
    update predicate that magic_link uses, so concurrent confirms can't
    both succeed.
    """
    __tablename__ = "pending_email_change"
    __table_args__ = (
        Index("ix_pending_email_change_account", "account_id"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    new_email: Mapped[str] = mapped_column(String(256), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
