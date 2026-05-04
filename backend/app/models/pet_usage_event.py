from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PetUsageEvent(Base):
    """Estimated usage ledger for pet calls, including fallback/cache events."""

    __tablename__ = "pet_usage_event"
    __table_args__ = (
        Index("ix_pet_usage_event_created_at", "created_at"),
        Index("ix_pet_usage_event_visitor_created", "visitor_hash", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visitor_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_level: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
