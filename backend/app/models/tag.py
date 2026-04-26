from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("slug", name="uq_tags_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#7dd3a4")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
