from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventLogArchive(Base):
    """Cold-storage mirror for event_log rows older than 90 days.

    Rows are inserted by the nightly ``prune_event_log`` worker, which
    afterwards deletes the source rows from ``event_log``. Archive rows
    older than 365 days are dropped during the same run.
    """

    __tablename__ = "event_log_archive"
    __table_args__ = (
        Index("ix_event_log_archive_created_at", "created_at"),
        Index("ix_event_log_archive_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
