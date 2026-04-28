"""Pydantic schemas for the danger zone admin API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class ExportJobItem(BaseModel):
    id: str
    status: Literal["pending", "running", "done", "failed"]
    requested_by: str
    file_size: int | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExportRequestResponse(BaseModel):
    job_id: str
    status: Literal["pending"]


class DeleteSiteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)
    handle: str = Field(min_length=1, max_length=64)


class ScheduleDeleteResponse(BaseModel):
    scheduled_at: datetime
    days_remaining: int


class DangerStatusResponse(BaseModel):
    pending_delete_at: datetime | None = None
    days_remaining: int | None = None
