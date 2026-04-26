from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("id = 1", name="ck_accounts_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    tfa_secret_encrypted: Mapped[str | None] = mapped_column(String(256))
    tfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    magic_link_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
