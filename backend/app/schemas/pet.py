from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.pet_defaults import DEFAULT_PERSONAS, DEFAULT_TEMPLATES

ProviderName = Literal["zhipu", "qwen", "doubao", "anthropic", "deepseek"]
PetMode = Literal[
    "greet",
    "idle_monologue",
    "summary_react",
    "selection_explain",
    "selection_qa",
    "free_chat",
    "follow_up",
    "article_finished",
    "reading_assist",
    "code_assist",
    "recommend_next",
    "pet_care",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ClientContext(_Loose):
    page_type: str | None = Field(default=None, max_length=24)
    path: str | None = Field(default=None, max_length=180)
    title: str | None = Field(default=None, max_length=160)
    tag: str | None = Field(default=None, max_length=40)
    read_progress: int | None = Field(default=None, ge=0, le=100)
    active_heading: str | None = Field(default=None, max_length=120)
    visible_block_type: str | None = Field(default=None, max_length=24)
    selection_kind: str | None = Field(default=None, max_length=24)
    dwell_seconds: int | None = Field(default=None, ge=0, le=3600)
    recent_action: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    active_tag: str | None = Field(default=None, max_length=40)
    post_count: int | None = Field(default=None, ge=0, le=1000)
    focused_post_title: str | None = Field(default=None, max_length=160)
    focused_post_tag: str | None = Field(default=None, max_length=40)
    focused_post_subtitle: str | None = Field(default=None, max_length=160)
    home_digest: str | None = Field(default=None, max_length=600)
    visible_posts: list[str] | None = Field(default=None, max_length=8)

    @field_validator(
        "page_type", "path", "title", "tag", "active_heading", "visible_block_type",
        "selection_kind", "recent_action", "locale", "timezone", "active_tag",
        "focused_post_title", "focused_post_tag", "focused_post_subtitle", "home_digest",
        mode="before",
    )
    @classmethod
    def _cap_context_strings(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        caps = {
            "page_type": 24,
            "path": 180,
            "title": 160,
            "tag": 40,
            "active_heading": 120,
            "visible_block_type": 24,
            "selection_kind": 24,
            "recent_action": 40,
            "locale": 32,
            "timezone": 64,
            "active_tag": 40,
            "focused_post_title": 160,
            "focused_post_tag": 40,
            "focused_post_subtitle": 160,
            "home_digest": 600,
        }
        return s[:caps.get(info.field_name, 120)] or None

    @field_validator("visible_posts", mode="before")
    @classmethod
    def _cap_visible_posts(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        items = [v] if isinstance(v, str) else list(v) if isinstance(v, (list, tuple)) else []
        capped = [str(item).strip()[:120] for item in items[:8] if str(item).strip()]
        return capped or None


class SummonRequest(_Strict):
    post_id: str | None = Field(default=None, max_length=64)
    selection: str | None = Field(default=None, max_length=4000)
    mode: PetMode | None = None
    message: str | None = Field(default=None, max_length=500)
    intent: str | None = Field(default=None, max_length=48)
    client_context: ClientContext | None = None

    @field_validator("message", "selection", "intent", mode="before")
    @classmethod
    def _strip_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


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
    free_chat: str = Field(default=DEFAULT_TEMPLATES["free_chat"], max_length=800)
    follow_up: str = Field(default=DEFAULT_TEMPLATES["follow_up"], max_length=800)
    article_finished: str = Field(default=DEFAULT_TEMPLATES["article_finished"], max_length=800)
    reading_assist: str = Field(default=DEFAULT_TEMPLATES["reading_assist"], max_length=800)
    code_assist: str = Field(default=DEFAULT_TEMPLATES["code_assist"], max_length=800)
    recommend_next: str = Field(default=DEFAULT_TEMPLATES["recommend_next"], max_length=800)
    pet_care: str = Field(default=DEFAULT_TEMPLATES["pet_care"], max_length=800)


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
    enable_free_chat: bool = True
    enable_proactive: bool = True
    enable_long_term_memory: bool = True
    per_mode_daily_limit: dict[str, int] = Field(
        default_factory=lambda: {
            "greet": 80,
            "idle_monologue": 20,
            "summary_react": 50,
            "selection_explain": 40,
            "selection_qa": 40,
            "free_chat": 60,
            "follow_up": 60,
            "article_finished": 10,
            "reading_assist": 30,
            "code_assist": 40,
            "recommend_next": 20,
            "pet_care": 0,
        },
        max_length=20,
    )
    per_mode_input_budget: dict[str, int] = Field(
        default_factory=lambda: {
            "greet": 400,
            "idle_monologue": 400,
            "summary_react": 700,
            "selection_explain": 1100,
            "selection_qa": 1100,
            "free_chat": 1300,
            "follow_up": 1100,
            "article_finished": 900,
            "reading_assist": 900,
            "code_assist": 1200,
            "recommend_next": 1000,
            "pet_care": 100,
        },
        max_length=20,
    )
    per_mode_output_budget: dict[str, int] = Field(
        default_factory=lambda: {
            "greet": 40,
            "idle_monologue": 35,
            "summary_react": 60,
            "selection_explain": 100,
            "selection_qa": 80,
            "free_chat": 100,
            "follow_up": 90,
            "article_finished": 70,
            "reading_assist": 70,
            "code_assist": 100,
            "recommend_next": 80,
            "pet_care": 20,
        },
        max_length=20,
    )

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
