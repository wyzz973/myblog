from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderName = Literal["zhipu", "qwen", "doubao", "anthropic"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PetConfig(_Strict):
    providers: list[ProviderName] = Field(
        default_factory=lambda: ["zhipu"],
        min_length=0,
        max_length=4,
    )
    system_prompt: str = Field(
        default=(
            "You are a tiny ASCII desktop pet on a developer's blog. "
            "Reply ONE short playful line (max 20 Chinese chars or 12 English words). "
            "Mix English/Chinese naturally. No quotes, no emoji."
        ),
        max_length=2000,
    )
    fallback_lines: list[str] = Field(
        min_length=1,
        default_factory=lambda: ["compiling thoughts..."],
    )
    tired_lines: list[str] = Field(
        min_length=1,
        default_factory=lambda: ["pets 累了…", "let me nap a bit, k?"],
    )
    per_ip_per_min: int = Field(default=6, ge=1, le=60)
    per_ip_per_day: int = Field(default=30, ge=1, le=500)
    global_per_day: int = Field(default=500, ge=10, le=10000)
    max_context_chars: int = Field(default=500, ge=100, le=2000)
    enable_article_context: bool = True
    enabled: bool = True
    species: str = Field(default="cat", max_length=32)
    hat: str = Field(default="none", max_length=32)
    tint: str = Field(default="#7aa7ff", max_length=16)
    visitor_can_change: bool = False

    @field_validator("providers")
    @classmethod
    def _dedupe_providers(cls, v: list[str]) -> list[str]:
        seen = set()
        out = []
        for p in v:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out


class PublicPetConfig(_Strict):
    species: str
    hat: str
    tint: str
    enabled: bool
    visitor_can_change: bool
