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
    # Raw markdown body. Only the admin endpoints populate it (so the editor
    # can round-trip an existing post); the public endpoint omits it.
    body_md: str | None = None
    likes: int
    word_count: int


class PostList(BaseModel):
    items: list[PostSummary]
    total: int
    limit: int
    offset: int
