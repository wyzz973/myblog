from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PetVisitorProfile(Base):
    """Low-sensitivity anonymous pet memory keyed by pet_vid-derived hash."""

    __tablename__ = "pet_visitor_profile"

    visitor_hash: Mapped[str] = mapped_column(String(16), primary_key=True)
    species: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str | None] = mapped_column(String(32))
    preferred_language: Mapped[str | None] = mapped_column(String(16))
    interest_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    recent_post_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    style_summary: Mapped[str | None] = mapped_column(Text)
    memory_summary: Mapped[str | None] = mapped_column(Text)
    proactive_muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
