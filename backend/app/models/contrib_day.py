from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContribDay(Base):
    __tablename__ = "contrib_days"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
