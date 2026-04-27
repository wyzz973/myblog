from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SiteMeta(Base, TimestampMixin):
    """Single-row site configuration table."""

    __tablename__ = "site_meta"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_meta_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    handle: Mapped[str] = mapped_column(String(64), nullable=False, default="wangyang")
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="汪洋")
    name_en: Mapped[str] = mapped_column(String(64), nullable=False, default="Wang Yang")
    role: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tagline: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    github: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pronouns: Mapped[str | None] = mapped_column(String(32))
    avatar_path: Mapped[str | None] = mapped_column(String(256))
    typing_line: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stack_chips: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    footer_note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    default_theme: Mapped[str] = mapped_column(String(8), nullable=False, default="dark")
    accent_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(82% 0.17 152)")
    accent2_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(80% 0.15 70)")
    violet_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(72% 0.18 295)")
    danger_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(70% 0.2 25)")
    launched_at: Mapped[date] = mapped_column(Date, nullable=False, default=date(2026, 1, 1))
    pet_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    avatar_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
