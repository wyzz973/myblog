from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PostFrontmatter(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    n: str = Field(pattern=r"^\d{3}$")
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = None
    tag: str = Field(min_length=1, max_length=32)
    date: date
    read: str | None = None
    lang: Literal["zh", "en"] = "zh"
    summary: str | None = None
    tldr: str | None = None
    status: Literal["draft", "published", "scheduled"] = "draft"
    scheduled_at: datetime | None = None
    featured: bool = False
    private: bool = False
    comments_enabled: bool = True

    @model_validator(mode="after")
    def _scheduled_must_have_when(self) -> "PostFrontmatter":
        if self.status == "scheduled" and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status=scheduled")
        return self
