from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PetConfig(_Strict):
    model: str = Field(default="claude-haiku-4-5-20251001", max_length=64)
    system_prompt: str = Field(default="You are wangyang.dev's desktop pet. Reply in 1 short sentence.", max_length=2000)
    fallback_lines: list[str] = Field(min_length=1, default_factory=lambda: ["compiling thoughts..."])
    rate_limit_per_min: int = Field(default=6, ge=1, le=60)
    enabled: bool = True
    species: Literal["cat", "dog", "rabbit", "fox"] = "cat"
    hat: str = Field(default="none", max_length=32)
    tint: str = Field(default="#7aa7ff", max_length=16)
    visitor_can_change: bool = False


class PublicPetConfig(_Strict):
    species: str
    hat: str
    tint: str
    enabled: bool
    visitor_can_change: bool
