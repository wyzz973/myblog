from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NowEntry(Base):
    __tablename__ = "now_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    listening: Mapped[str | None] = mapped_column(String(256))
    reading: Mapped[str | None] = mapped_column(String(256))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
