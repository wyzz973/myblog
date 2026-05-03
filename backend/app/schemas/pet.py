from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.pet_defaults import DEFAULT_PERSONAS, DEFAULT_TEMPLATES

ProviderName = Literal["zhipu", "qwen", "doubao", "anthropic", "deepseek"]
PetMode = Literal["greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PetPersonas(_Strict):
    duck: str = Field(default=DEFAULT_PERSONAS["duck"], max_length=400)
    goose: str = Field(default=DEFAULT_PERSONAS["goose"], max_length=400)
    blob: str = Field(default=DEFAULT_PERSONAS["blob"], max_length=400)
    cat: str = Field(default=DEFAULT_PERSONAS["cat"], max_length=400)
    rabbit: str = Field(default=DEFAULT_PERSONAS["rabbit"], max_length=400)
    penguin: str = Field(default=DEFAULT_PERSONAS["penguin"], max_length=400)
    owl: str = Field(default=DEFAULT_PERSONAS["owl"], max_length=400)
    turtle: str = Field(default=DEFAULT_PERSONAS["turtle"], max_length=400)
    capybara: str = Field(default=DEFAULT_PERSONAS["capybara"], max_length=400)
    mushroom: str = Field(default=DEFAULT_PERSONAS["mushroom"], max_length=400)
    ghost: str = Field(default=DEFAULT_PERSONAS["ghost"], max_length=400)
    snail: str = Field(default=DEFAULT_PERSONAS["snail"], max_length=400)
    cactus: str = Field(default=DEFAULT_PERSONAS["cactus"], max_length=400)
    chonk: str = Field(default=DEFAULT_PERSONAS["chonk"], max_length=400)
    octopus: str = Field(default=DEFAULT_PERSONAS["octopus"], max_length=400)
    jellyfish: str = Field(default=DEFAULT_PERSONAS["jellyfish"], max_length=400)
    axolotl: str = Field(default=DEFAULT_PERSONAS["axolotl"], max_length=400)
    robot: str = Field(default=DEFAULT_PERSONAS["robot"], max_length=400)
    dragon: str = Field(default=DEFAULT_PERSONAS["dragon"], max_length=400)
    phoenix: str = Field(default=DEFAULT_PERSONAS["phoenix"], max_length=400)
    fox: str = Field(default=DEFAULT_PERSONAS["fox"], max_length=400)
    shiba: str = Field(default=DEFAULT_PERSONAS["shiba"], max_length=400)
    mochi: str = Field(default=DEFAULT_PERSONAS["mochi"], max_length=400)
    panda: str = Field(default=DEFAULT_PERSONAS["panda"], max_length=400)
    hamster: str = Field(default=DEFAULT_PERSONAS["hamster"], max_length=400)
    bee: str = Field(default=DEFAULT_PERSONAS["bee"], max_length=400)
    otter: str = Field(default=DEFAULT_PERSONAS["otter"], max_length=400)


class PetModeTemplates(_Strict):
    greet: str = Field(default=DEFAULT_TEMPLATES["greet"], max_length=800)
    idle_monologue: str = Field(default=DEFAULT_TEMPLATES["idle_monologue"], max_length=800)
    summary_react: str = Field(default=DEFAULT_TEMPLATES["summary_react"], max_length=800)
    selection_explain: str = Field(default=DEFAULT_TEMPLATES["selection_explain"], max_length=800)
    selection_qa: str = Field(default=DEFAULT_TEMPLATES["selection_qa"], max_length=800)


class PetConfig(_Strict):
    providers: list[ProviderName] = Field(
        default_factory=lambda: ["zhipu"],
        min_length=0,
        max_length=5,
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
    per_ip_per_min: int = Field(default=6, ge=1, le=120)
    per_ip_per_day: int = Field(default=30, ge=1, le=10000)
    global_per_day: int = Field(default=500, ge=10, le=100000)
    max_context_chars: int = Field(default=500, ge=100, le=2000)
    summary_max_chars: int = Field(default=200, ge=50, le=1000)
    enable_article_context: bool = True
    enabled: bool = True
    species: str = Field(default="cat", max_length=32)
    hat: str = Field(default="none", max_length=32)
    tint: str = Field(default="#7aa7ff", max_length=16)
    visitor_can_change: bool = False

    # NEW
    personas: PetPersonas = Field(default_factory=PetPersonas)
    mode_templates: PetModeTemplates = Field(default_factory=PetModeTemplates)
    unlimited: bool = False
    hard_ceiling_per_day: int = Field(default=20000, ge=100, le=100000)
    context_window_turns: int = Field(default=10, ge=1, le=50)
    context_ttl_seconds: int = Field(default=7200, ge=60, le=86400)

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
    species: str  # admin's preview/default species (legacy)
    assigned_species: str  # deterministic per-visitor — bound to (ip, user_agent)
    hat: str
    tint: str
    enabled: bool
    visitor_can_change: bool
