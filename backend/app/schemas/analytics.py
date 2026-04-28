"""Pydantic schemas for the analytics admin + public APIs."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# --- public hit beacon ---


class HitRequest(BaseModel):
    path: str = Field(max_length=512)
    referrer: str | None = Field(default=None, max_length=512)
    post_id: str | None = Field(default=None, max_length=64)


# --- dashboard KPIs ---


class HitsKPI(BaseModel):
    today: int
    last_7d: int
    last_30d: int


class LikesKPI(BaseModel):
    total: int
    last_7d: int


class CommentsKPI(BaseModel):
    total: int
    pending: int


class PostsKPI(BaseModel):
    published: int
    draft: int
    scheduled: int


class MediaKPI(BaseModel):
    count: int


class DashboardResponse(BaseModel):
    hits: HitsKPI
    likes: LikesKPI
    comments: CommentsKPI
    posts: PostsKPI
    media: MediaKPI


# --- analytics bundle ---


class DayPoint(BaseModel):
    date: date
    hits: int


class PathHits(BaseModel):
    path: str
    hits: int


class ReferrerHits(BaseModel):
    referrer: str
    hits: int


class CountryHits(BaseModel):
    country: str
    hits: int


class AnalyticsBundleResponse(BaseModel):
    timeseries: list[DayPoint]
    top_paths: list[PathHits]
    top_referrers: list[ReferrerHits]
    top_countries: list[CountryHits]


# --- per-post + per-tag ---


class PostHitsItem(BaseModel):
    post_id: str
    title: str
    hits: int


class TagHitsItem(BaseModel):
    tag_id: int
    slug: str
    name: str
    hits: int
