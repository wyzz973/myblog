from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApiTokenUsage(Base):
    """Per-request log row for api-token-scoped admin calls (Task 29).

    Inserted in api_tokens_svc.touch_last_used; queried by the admin UI's
    per-token usage panel. Older rows can be pruned by a future cron, but
    for single-author volume the natural growth is bounded.
    """
    __tablename__ = "api_token_usage"
    __table_args__ = (
        Index(
            "ix_api_token_usage_token_used",
            "api_token_id",
            text("used_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_token_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        nullable=False,
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    status_code: Mapped[int | None] = mapped_column(SmallInteger)
