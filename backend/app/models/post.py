from datetime import date as date_t, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.tag import Tag


class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','published','scheduled')", name="ck_posts_status"
        ),
        CheckConstraint("lang in ('zh','en')", name="ck_posts_lang"),
        Index("ix_posts_status_date", "status", "date"),
        Index("ix_posts_tag_status_date", "tag_id", "status", "date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    n: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="RESTRICT"), nullable=False
    )
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    read: Mapped[str | None] = mapped_column(String(16))
    lang: Mapped[str] = mapped_column(String(2), nullable=False, default="zh")
    summary: Mapped[str | None] = mapped_column(Text)
    tldr: Mapped[str | None] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    body_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comments_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tag: Mapped[Tag] = relationship(lazy="joined")
