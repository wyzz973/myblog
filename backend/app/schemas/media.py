"""Pydantic schemas for the media admin API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    id: int
    filename: str
    url: str
    mime_type: str
    size: int
    width: int | None = None
    height: int | None = None
    alt: str | None = None
    created_at: datetime


class MediaPatch(BaseModel):
    alt: str | None = Field(default=None, max_length=512)


class MediaUploadFailure(BaseModel):
    filename: str
    error: str


class MediaUploadResponse(BaseModel):
    ok: list[MediaItem]
    failed: list[MediaUploadFailure]
