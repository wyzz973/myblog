from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HitEvent(Base):
    __tablename__ = "hit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    referrer: Mapped[str | None] = mapped_column(String(512))
    country: Mapped[str | None] = mapped_column(CHAR(2))
    post_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
