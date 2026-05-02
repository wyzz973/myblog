from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PetMessage(Base):
    """Permanent archive of every pet summon turn.

    Companion to the Redis short-term context (pet_context.py): Redis
    holds the live 10-turn window for LLM injection; this table holds
    the durable history admins can browse, search, and analyze.
    """

    __tablename__ = "pet_message"
    __table_args__ = (
        Index("ix_pet_message_visitor_hash_created", "visitor_hash", "created_at"),
        Index("ix_pet_message_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visitor_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    species: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    post_id: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str | None] = mapped_column(String(200))
    tag_slug: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[str | None] = mapped_column(Text)
    selection: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prior_turns: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
