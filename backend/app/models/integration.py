from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint("name IN ('github','anthropic')", name="ck_integrations_name"),
    )

    name: Mapped[str] = mapped_column(String(16), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    extra_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
