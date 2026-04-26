from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NowEntryItem(_Strict):
    id: int
    body_md: str
    listening: str | None = None
    reading: str | None = None
    is_current: bool
    created_at: datetime


class NowCreateRequest(_Strict):
    body_md: str = Field(min_length=1, max_length=5000)
    listening: str | None = Field(default=None, max_length=256)
    reading: str | None = Field(default=None, max_length=256)
    is_current: bool = False


class NowPatchRequest(_Strict):
    body_md: str | None = Field(default=None, min_length=1, max_length=5000)
    listening: str | None = Field(default=None, max_length=256)
    reading: str | None = Field(default=None, max_length=256)
    is_current: bool | None = None


class NowPublicResponse(_Strict):
    current: NowEntryItem | None = None
    history: list[NowEntryItem]
