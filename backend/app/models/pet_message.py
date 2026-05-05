from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
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
    # Free-form: not a FK to posts.id. Archive must survive post deletion;
    # if a post is later deleted, this column keeps the snapshot for history.
    post_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(200))
    tag_slug: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[str | None] = mapped_column(Text)
    selection: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(48))
    client_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prior_turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_level: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
