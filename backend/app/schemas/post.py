from datetime import date as date_t, datetime
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
    # Total like count. Public list endpoints leave this at 0 (likes are
    # not exposed on the home feed); admin list populates per-post.
    likes: int = 0


class PostDetail(PostSummary):
    tldr: str | None
    body: list[dict[str, Any]]
    # Raw markdown body. Only the admin endpoints populate it (so the editor
    # can round-trip an existing post); the public endpoint omits it.
    body_md: str | None = None
    likes: int
    word_count: int
    # Lifecycle / visibility flags — admin-only on the response so the editor
    # can preserve them when serializing back to frontmatter on save.
    status: str | None = None
    scheduled_at: datetime | None = None
    featured: bool | None = None
    private: bool | None = None
    comments_enabled: bool | None = None


class PostList(BaseModel):
    items: list[PostSummary]
    total: int
    limit: int
    offset: int
