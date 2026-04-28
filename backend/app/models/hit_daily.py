from datetime import date as date_type

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HitDaily(Base):
    __tablename__ = "hit_daily"

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    path: Mapped[str] = mapped_column(String(512), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
    post_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="SET NULL")
    )
    referrers_top: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    countries_top: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
