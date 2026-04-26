from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GithubIntegrationGet(_Strict):
    username: str | None = None
    last_synced_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


class GithubIntegrationPut(_Strict):
    username: str = Field(min_length=1, max_length=64)
    token: str = Field(min_length=1, max_length=256)


class AnthropicIntegrationGet(_Strict):
    model: str | None = None
    last_status: str | None = None
    last_error: str | None = None


class AnthropicIntegrationPut(_Strict):
    api_key: str = Field(min_length=1, max_length=256)
    model: str | None = Field(default=None, max_length=64)
