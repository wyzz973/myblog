from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventLog(Base):
    __tablename__ = "event_log"
    __table_args__ = (
        Index("ix_event_log_created_at", "created_at"),
        Index("ix_event_log_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    target: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
