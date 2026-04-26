from datetime import date as date_t
from typing import Any

from pydantic import BaseModel


class PostSummary(BaseModel):
    id: str
    n: str
    title: str
    subtitle: str | None
    tag: str   # slug
    date: date_t
    read: str | None
    lang: str
    summary: str | None


class PostDetail(PostSummary):
    tldr: str | None
    body: list[dict[str, Any]]
    likes: int
    word_count: int


class PostList(BaseModel):
    items: list[PostSummary]
    total: int
    limit: int
    offset: int
