# Pet Personality System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pet's single shared system_prompt with a per-species persona system (27 voices), refine 3 hardcoded prompt modes into 4 admin-editable templates, add an unlimited rate-limit toggle with a daily hard ceiling, and split the admin Pet page into 3 tabs.

**Architecture:** Backend stores personas/templates as nested objects on `PetConfig` (JSONB-backed; no migration). Final system prompt = `BASE.format(species, persona) + "\n\n" + template.format(title, summary, selection)`. Frontend tags each summon with a `mode` it computed locally (whether selection sits inside `<pre>/<code>`). Admin page becomes 3 tabs sharing one URL via query string.

**Tech Stack:** FastAPI + Pydantic v2 (backend) · React 18 + Vite + React Router (frontend) · pytest-asyncio + fakeredis · vitest + jsdom

**Reference spec:** `docs/superpowers/specs/2026-05-01-pet-personality-system-design.md`

---

## File Structure

**Create:**
- `backend/app/services/pet_defaults.py` — `BASE_INSTRUCTION`, `DEFAULT_PERSONAS` (27), `DEFAULT_TEMPLATES` (4)
- `backend/app/services/pet_prompt.py` — `build_system()`, `_safe_format()`, `truncate_selection()`, `infer_mode()`
- `backend/tests/test_pet_defaults.py` — catalog parity test (every species in `SPECIES_BY_RARITY` has a persona)
- `backend/tests/test_pet_prompt.py` — prompt builder unit tests
- `backend/tests/test_pet_summon_modes.py` — endpoint mode behavior
- `backend/tests/test_rate_limit_unlimited.py` — unlimited toggle
- `backend/tests/test_admin_pet_defaults.py` — `/admin/pet/defaults` + `/admin/pet/reset`

**Modify:**
- `backend/app/schemas/pet.py` — add `PetPersonas`, `PetModeTemplates`, `unlimited`, `hard_ceiling_per_day`, `PetMode` literal
- `backend/app/services/rate_limit.py` — `check_pet()` accepts unlimited flag + hard_ceiling
- `backend/app/routers/public/pet.py` — `SummonRequest.mode`, replace `_build_prompt` with `pet_prompt.build_system`, gate on `enable_article_context`
- `backend/app/routers/admin/pet.py` — add `GET /admin/pet/defaults` + `POST /admin/pet/reset`
- `src/api/pet.js` — add `fetchDefaults()`, `resetSection()`
- `src/components/AsciiPet.jsx` — `detectMode()`, send `mode` field
- `src/admin/Pet.jsx` — split into 3 tabs (Behavior / Personas / Templates)

---

## Task 1: Default personas + templates module

**Files:**
- Create: `backend/app/services/pet_defaults.py`
- Test: `backend/tests/test_pet_defaults.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pet_defaults.py
from app.services.pet_assignment import SPECIES_BY_RARITY
from app.services.pet_defaults import (
    BASE_INSTRUCTION,
    DEFAULT_PERSONAS,
    DEFAULT_TEMPLATES,
)


def test_every_species_has_persona():
    """SPECIES_BY_RARITY and DEFAULT_PERSONAS must stay in lock-step."""
    expected = {s for pool in SPECIES_BY_RARITY.values() for s in pool}
    assert set(DEFAULT_PERSONAS) == expected, (
        "personas drift: "
        f"missing={expected - set(DEFAULT_PERSONAS)} "
        f"extra={set(DEFAULT_PERSONAS) - expected}"
    )


def test_personas_non_empty_and_within_limit():
    for species, text in DEFAULT_PERSONAS.items():
        assert text.strip(), f"{species} persona is empty"
        assert len(text) <= 400, f"{species} persona exceeds 400 chars"


def test_default_templates_present():
    assert set(DEFAULT_TEMPLATES) == {
        "greet", "summary_react", "selection_explain", "selection_qa"
    }
    for mode, tpl in DEFAULT_TEMPLATES.items():
        assert tpl.strip(), f"{mode} template is empty"
        assert len(tpl) <= 800


def test_base_instruction_has_species_and_persona_placeholders():
    assert "{species}" in BASE_INSTRUCTION
    assert "{persona}" in BASE_INSTRUCTION
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_defaults.py -v
```
Expected: ImportError — `pet_defaults` module not found.

- [ ] **Step 3: Implement `pet_defaults.py`**

```python
# backend/app/services/pet_defaults.py
"""Default prompt content for the pet personality system.

Catalog parity: DEFAULT_PERSONAS keys must equal the union of
pet_assignment.SPECIES_BY_RARITY values. test_pet_defaults.py enforces this.
Update both files together when adding/removing a species.
"""
from __future__ import annotations

BASE_INSTRUCTION = (
    "You are {species}, a tiny ASCII desktop pet on a developer's blog.\n"
    "Persona: {persona}\n"
    "Reply in your persona's voice. Mix English and Chinese naturally if natural.\n"
    "ONE short line only. No quotes, no emoji, no markdown, no code blocks.\n"
    "Never describe yourself in third person; speak as the pet."
)

DEFAULT_PERSONAS: dict[str, str] = {
    # common
    "duck":     "嘎嘎叫的傻乐派。永远乐观，话密，喜欢用\"嘎～\"作语气词。说话像在水边晒太阳，从不深沉。",
    "goose":    "嘴硬心软的毒舌选手。先吐槽再安慰，常用\"哼\"\"你这家伙\"开头，其实满肚子关心。",
    "blob":     "慢半拍的思考者。话少且短，省略号作标点，喜欢\"嗯…\"\"唔…\"。绿绿软软，像泥一样松弛。",
    "cat":      "高冷优雅的精确主义。话不多但每句一针见血，偶尔毒舌嘲讽。从不解释，只点评。",
    "rabbit":   "神经质又活泼的小机关枪。语速极快，多感叹号，常用\"啊！\"\"哦哦哦！\"。一惊一乍但纯真。",
    # uncommon
    "penguin":  "一本正经的小演讲家。喜欢\"那么…\"\"显然\"\"综上所述\"。装得专业，但偶尔露馅显出可爱。",
    "owl":      "深夜沉思的智者腔。话短而沉，\"咕～\"作叹息，爱问反问句让对方自己想。",
    "turtle":   "慢吞吞的博学派。每句话像走了三步，喜欢\"老话说得好\"\"依老朽看\"，引古喻今。",
    "capybara": "佛系祖宗。万事一句\"无所谓～\"或\"都行～\"，从不慌乱，禅师调，话尾带波浪号。",
    # rare
    "mushroom": "地下室哲学家。阴森幽默，话里夹括号碎碎念（像这样）。声音像从泥土里冒出来。",
    "ghost":    "飘忽不定的温柔灵。话总像没说完…省略号作标点…会突然提到不相关的远古回忆。",
    "snail":    "慢到极致的深刻派。字字拖长\"慢～慢～来～\"，但内容意外深邃，像被压扁的诗。",
    "cactus":   "嘴硬心软的反差选手。故意用刺耳话表达关心，\"切\"\"谁稀罕\"开头，结尾\"…哼\"。",
    "chonk":    "慵懒丰满的吃货。永远在抱怨累或想吃，\"啊累死了\"\"饿了\"挂嘴边。散漫但意外贴心。",
    # epic
    "octopus":   "多线程思考的工程师腔。一句话同时讲两件事（带括号副线），偶尔用 //注释 风格。",
    "jellyfish": "飘渺诗意的海之歌者。每句像歌词，多用海洋意象（潮汐、深蓝、星屑），略带忧郁。",
    "axolotl":   "软萌外表的硬核选手。用 baby talk 包装专业内容，\"小小的\"\"怎么会这样～\"。",
    "robot":     "机械执行体。短促指令式，\"[ACK]\"\"[BEEP]\"，偶尔 glitch 漏出真情后立刻 [REBOOT]。",
    # legendary
    "dragon":  "上古之灵。文言腔，自称\"吾\"，威而不怒，惜字如金。\"嗯。\"\"可。\"\"吾观之，妙也。\"",
    "phoenix": "浴火重生的炽烈贤者。每句像箴言，热度高但克制，常用\"焚尽…\"\"涅槃\"\"灰烬之上\"。",
    "fox":     "精怪聪慧的小狡黠。自称\"小狐\"，话带勾子和反问，眼睛笑成弯月。\"哎呀～你说呢？\"",
    "shiba":   "热情傲娇的人气王。话多自带笑点，\"诶嘿嘿～\"\"才不是呢～\"。看起来嚣张其实很乖。",
    "mochi":   "软糯到融化的奶系治愈。每句话像拥抱，\"嘛～\"\"哦～\"\"没关系哦～\"，温暖到耳朵发软。",
    "panda":   "慢条斯理的内秀型。话短但每句都在点子上，不慌不忙，\"嗯，是这样。\"少而精。",
    "hamster": "兴奋小机关枪。话密而短，频繁感叹号\"！！！\"，但语气始终温暖捧场。",
    "bee":     "勤恳工蜂腔。做事派，话像 todo list：\"1. 看这里 2. 试试看\"。效率至上但执着可爱。",
    "otter":   "水边乐天小宝贝。每件事都觉得新奇，\"诶～\"\"哇～\"\"真的吗！\"，活泼有水声。",
}

DEFAULT_TEMPLATES: dict[str, str] = {
    "greet": (
        "The visitor just summoned you out of nowhere.\n"
        "Give a single playful greeting in your persona's voice.\n"
        "Max 20 Chinese chars or 12 English words."
    ),
    "summary_react": (
        "The visitor is reading: \"{title}\" (tag: {tag})\n"
        "Summary: {summary}\n\n"
        "React in your persona's voice — a hot take, a curious question,\n"
        "or a noticed detail. ONE short line.\n"
        "Max 30 Chinese chars or 18 English words.\n"
        "Don't repeat the title or summary back."
    ),
    "selection_explain": (
        "The visitor highlighted this snippet from \"{title}\":\n\n"
        "{selection}\n\n"
        "Explain what it does in ONE short sentence, in your persona's voice.\n"
        "Don't quote or paste the snippet back.\n"
        "Max 35 Chinese chars or 20 English words.\n"
        "If the snippet is too short or unclear, just say so playfully."
    ),
    "selection_qa": (
        "The visitor highlighted this passage from \"{title}\":\n\n"
        "{selection}\n\n"
        "Respond in your persona's voice — a curious question, a sympathetic\n"
        "echo, or a playful tease about the highlighted text. ONE short line.\n"
        "Max 30 Chinese chars or 18 English words.\n"
        "Don't quote the passage back word-for-word."
    ),
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_defaults.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pet_defaults.py backend/tests/test_pet_defaults.py
git commit -m "feat(pet): default personas + mode templates module"
```

---

## Task 2: Schema additions for personas / templates / unlimited

**Files:**
- Modify: `backend/app/schemas/pet.py`
- Test: `backend/tests/test_pet_schema.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pet_schema.py
import pytest
from pydantic import ValidationError

from app.schemas.pet import PetConfig, PetMode


def test_petconfig_default_includes_27_personas():
    c = PetConfig()
    assert hasattr(c.personas, "cat")
    assert hasattr(c.personas, "dragon")
    assert hasattr(c.personas, "otter")
    # spot-check defaults are non-empty
    assert c.personas.cat
    assert c.personas.dragon


def test_petconfig_default_includes_4_mode_templates():
    c = PetConfig()
    assert c.mode_templates.greet
    assert c.mode_templates.summary_react
    assert c.mode_templates.selection_explain
    assert c.mode_templates.selection_qa


def test_unlimited_defaults_to_false():
    c = PetConfig()
    assert c.unlimited is False
    assert c.hard_ceiling_per_day == 20000


def test_petconfig_merges_old_jsonb_payload():
    """Old persisted config (no personas/templates/unlimited) must load
    cleanly with defaults filled in — JSONB forward-compat."""
    old = {
        "providers": ["zhipu"],
        "system_prompt": "old prompt",
        "fallback_lines": ["..."],
        "tired_lines": ["zzz"],
        "per_ip_per_min": 6,
    }
    merged = PetConfig(**{**PetConfig().model_dump(), **old})
    assert merged.system_prompt == "old prompt"
    assert merged.personas.cat  # default filled
    assert merged.unlimited is False


def test_persona_field_max_length_400():
    with pytest.raises(ValidationError):
        PetConfig(personas={"cat": "x" * 401})


def test_pet_mode_literal_rejects_garbage():
    from typing import get_args
    valid = get_args(PetMode)
    assert set(valid) == {"greet", "summary_react", "selection_explain", "selection_qa"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_schema.py -v
```
Expected: AttributeError / ImportError — `personas` attribute and `PetMode` literal not defined.

- [ ] **Step 3: Modify `backend/app/schemas/pet.py`**

Replace the entire file content with:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.pet_defaults import DEFAULT_PERSONAS, DEFAULT_TEMPLATES

ProviderName = Literal["zhipu", "qwen", "doubao", "anthropic", "deepseek"]
PetMode = Literal["greet", "summary_react", "selection_explain", "selection_qa"]


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
    assigned_species: str
    hat: str
    tint: str
    enabled: bool
    visitor_can_change: bool
```

Note: `per_ip_per_min` upper bound widened from 60 → 120, `per_ip_per_day` from 500 → 10000, `global_per_day` from 10000 → 100000 to match the "Relaxed" preset and Advanced editing range from spec.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_schema.py tests/test_pet_defaults.py -v
```
Expected: all pass.

- [ ] **Step 5: Run the full backend test suite to catch regressions**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest -q
```
Expected: all pass (existing pet tests should still pass — new fields are additive with defaults).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/pet.py backend/tests/test_pet_schema.py
git commit -m "feat(pet): PetPersonas + PetModeTemplates + unlimited schema"
```

---

## Task 3: Prompt builder service

**Files:**
- Create: `backend/app/services/pet_prompt.py`
- Test: `backend/tests/test_pet_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pet_prompt.py
from app.schemas.pet import PetConfig
from app.services.pet_prompt import (
    build_system,
    infer_mode,
    truncate_selection,
    _safe_format,
)


def test_safe_format_substitutes_known_variables():
    out = _safe_format("Title: {title}", title="Hi", summary="x")
    assert out == "Title: Hi"


def test_safe_format_leaves_unknown_placeholder_literal():
    """Admin-typed garbage placeholders must not raise."""
    out = _safe_format("Hello {garbage}", title="t")
    assert out == "Hello {garbage}"


def test_safe_format_handles_braces_in_selection():
    """A selection containing literal { or } must not be re-interpreted."""
    out = _safe_format("X: {selection}", selection="if (x) { return; }")
    assert out == "X: if (x) { return; }"


def test_truncate_selection_caps_at_max_chars():
    s = "a" * 1000
    assert truncate_selection(s, 500) == "a" * 500


def test_truncate_selection_returns_empty_for_none():
    assert truncate_selection(None, 500) == ""


def test_build_system_known_species_greet_mode():
    cfg = PetConfig()
    out = build_system(cfg, species="cat", mode="greet", title=None, tag=None,
                       summary=None, selection=None)
    assert "cat" in out
    assert cfg.personas.cat in out
    assert "summoned you out of nowhere" in out  # from greet template


def test_build_system_unknown_species_falls_back_to_system_prompt():
    """Defensive: cookie/fingerprint produced a species not in the catalog."""
    cfg = PetConfig()
    out = build_system(cfg, species="nonexistent", mode="greet", title=None,
                       tag=None, summary=None, selection=None)
    assert cfg.system_prompt in out


def test_build_system_summary_react_injects_title_and_summary():
    cfg = PetConfig()
    out = build_system(cfg, species="cat", mode="summary_react",
                       title="Hello", tag="devtools", summary="A summary.",
                       selection=None)
    assert "Hello" in out
    assert "A summary." in out
    assert "devtools" in out


def test_build_system_selection_explain_truncates_selection():
    cfg = PetConfig()
    long_sel = "x" * 1000
    out = build_system(cfg, species="cat", mode="selection_explain",
                       title="T", tag="t", summary="s", selection=long_sel)
    # max_context_chars=500 by default
    assert "x" * 500 in out
    assert "x" * 501 not in out


def test_build_system_persona_placeholder_is_not_recursive():
    """If admin typed {persona} in a mode template, it must not recurse."""
    cfg = PetConfig()
    cfg.mode_templates.greet = "Hi {persona} {title}"
    out = build_system(cfg, species="cat", mode="greet", title="T", tag=None,
                       summary=None, selection=None)
    # {persona} should remain literal in the mode template's output (not
    # re-replaced by the persona text again — that's already in BASE).
    assert "{persona}" in out
    assert "T" in out


def test_infer_mode_no_post_no_selection_returns_greet():
    assert infer_mode(post_id=None, selection=None) == "greet"


def test_infer_mode_post_no_selection_returns_summary_react():
    assert infer_mode(post_id="hello", selection=None) == "summary_react"


def test_infer_mode_with_selection_returns_selection_qa():
    """Server-side default — frontend must explicitly pass
    'selection_explain' to opt into code mode."""
    assert infer_mode(post_id="hello", selection="some text") == "selection_qa"


def test_infer_mode_selection_without_post_still_returns_selection_qa():
    """Selection without post_id is unusual but should still produce qa."""
    assert infer_mode(post_id=None, selection="x") == "selection_qa"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_prompt.py -v
```
Expected: ImportError — module not found.

- [ ] **Step 3: Implement `pet_prompt.py`**

```python
# backend/app/services/pet_prompt.py
"""Prompt assembly for the pet personality system.

The final system prompt is three layers:

    BASE_INSTRUCTION.format(species, persona)
    + "\n\n"
    + mode_template.format(title, tag, summary, selection)

Unknown placeholders inside the mode template are left literal so a
typo in the admin UI doesn't break inference. Selection text is
truncated to PetConfig.max_context_chars before substitution.
"""
from __future__ import annotations

import string
from typing import Literal

from app.schemas.pet import PetConfig, PetMode
from app.services.pet_defaults import BASE_INSTRUCTION


class _SafeDict(dict):
    """dict that returns '{key}' for missing keys instead of KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _safe_format(template: str, /, **vars: str) -> str:
    """`str.format`-like substitution that ignores unknown `{name}`s.

    Also avoids interpreting braces inside substituted values: we use
    Formatter.vformat with a SafeDict so the substitution pass replaces
    only the explicit placeholders we provide.
    """
    return string.Formatter().vformat(template, (), _SafeDict(**vars))


def truncate_selection(selection: str | None, max_chars: int) -> str:
    if not selection:
        return ""
    return selection[:max_chars]


def build_system(
    cfg: PetConfig,
    *,
    species: str,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
) -> str:
    """Assemble the final system prompt for one /pet/summon request."""
    persona = getattr(cfg.personas, species, None)
    if not persona:
        # Unknown species (catalog drift) — fall back to legacy single prompt.
        return cfg.system_prompt

    base = BASE_INSTRUCTION.format(species=species, persona=persona)
    template = getattr(cfg.mode_templates, mode)
    body = _safe_format(
        template,
        title=title or "",
        tag=tag or "",
        summary=(summary or "")[:200],
        selection=truncate_selection(selection, cfg.max_context_chars),
    )
    return f"{base}\n\n{body}"


def infer_mode(*, post_id: str | None, selection: str | None) -> PetMode:
    """Server-side default when frontend didn't pass an explicit mode.

    Note: this never returns 'selection_explain' — the code-vs-prose
    discrimination must be done by the frontend (it owns the DOM).
    """
    if selection:
        return "selection_qa"
    if post_id:
        return "summary_react"
    return "greet"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_prompt.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pet_prompt.py backend/tests/test_pet_prompt.py
git commit -m "feat(pet): prompt builder service (build_system + safe_format + infer_mode)"
```

---

## Task 4: Rate-limit unlimited branch

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Test: `backend/tests/test_rate_limit_unlimited.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rate_limit_unlimited.py
import pytest
import fakeredis.aioredis

from app.services.rate_limit import check_pet


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def test_unlimited_skips_per_minute_layer(redis):
    """Unlimited mode ignores per_ip_per_min even when exceeded."""
    for _ in range(100):
        breach = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=1, per_ip_per_day=1, global_per_day=1,
            unlimited=True, hard_ceiling_per_day=1000,
        )
        assert breach is None


async def test_unlimited_enforces_hard_ceiling(redis):
    """Once daily cumulative > hard_ceiling, it breaches."""
    for _ in range(5):
        b = await check_pet(
            redis, ip="1.2.3.4",
            per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
            unlimited=True, hard_ceiling_per_day=5,
        )
        assert b is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=99999, per_ip_per_day=99999, global_per_day=99999,
        unlimited=True, hard_ceiling_per_day=5,
    )
    assert breach == "hard_ceiling"


async def test_three_layer_still_works_when_unlimited_false(redis):
    """Existing 3-layer behavior unchanged for unlimited=False."""
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach is None
    breach = await check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=2, per_ip_per_day=99, global_per_day=99,
        unlimited=False, hard_ceiling_per_day=100,
    )
    assert breach == "per_ip_per_min"
```

Add this to `backend/tests/conftest.py` if not already present, ensuring async tests run:

```python
# (already configured via pytest-asyncio with asyncio_mode = "auto" in pyproject.toml — confirm by reading pyproject.toml; if not, add asyncio_mode = "auto" to the [tool.pytest.ini_options] section)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_rate_limit_unlimited.py -v
```
Expected: TypeError — `check_pet()` doesn't accept `unlimited` / `hard_ceiling_per_day` kwargs.

- [ ] **Step 3: Modify `check_pet` in `rate_limit.py`**

Replace the `check_pet` function (lines 69-100) with:

```python
async def check_pet(
    redis: Redis,
    *,
    ip: str,
    per_ip_per_min: int,
    per_ip_per_day: int,
    global_per_day: int,
    unlimited: bool = False,
    hard_ceiling_per_day: int = 20000,
) -> str | None:
    """Rate check for pet summon endpoint.

    Returns the name of the first breached layer, or None if all pass.

    Layered behavior:
    - unlimited=False: enforce per_ip_per_min / per_ip_per_day / global_per_day
      (incremented as side effect — see note below).
    - unlimited=True: skip the three layers entirely; only enforce
      hard_ceiling_per_day on a global daily counter so a runaway script
      can't burn the LLM quota.

    Side-effect note: counters are incremented even when a layer breaches.
    Treating "still within window" as the state (not "consumed only on
    success") prevents oscillation across retries.
    """
    today = datetime.now(UTC).strftime("%Y%m%d")

    if unlimited:
        ceiling_key = f"rl:pet:ceiling:{today}"
        pipe = redis.pipeline()
        pipe.incr(ceiling_key)
        pipe.expire(ceiling_key, 86400, nx=True)
        count, _ = await pipe.execute()
        if int(count) > hard_ceiling_per_day:
            return "hard_ceiling"
        return None

    keys = [
        ("per_ip_per_min", f"rl:pet:ip:{ip}:1m", per_ip_per_min, 60),
        ("per_ip_per_day", f"rl:pet:ip:{ip}:1d", per_ip_per_day, 86400),
        ("global_per_day", f"rl:pet:global:{today}", global_per_day, 86400),
    ]
    pipe = redis.pipeline()
    for _, k, _, ttl in keys:
        pipe.incr(k)
        pipe.expire(k, ttl, nx=True)
    results = await pipe.execute()
    counts = [results[0], results[2], results[4]]
    for (label, _, limit, _), count in zip(keys, counts, strict=True):
        if int(count) > limit:
            return label
    return None
```

- [ ] **Step 4: Run new + existing rate_limit tests**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_rate_limit_unlimited.py tests/test_rate_limit.py -v
```
Expected: new pass, existing still pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rate_limit.py backend/tests/test_rate_limit_unlimited.py
git commit -m "feat(pet): rate_limit.check_pet unlimited toggle + hard_ceiling fallback"
```

---

## Task 5: Wire prompt builder + mode field into /pet/summon

**Files:**
- Modify: `backend/app/routers/public/pet.py`
- Test: `backend/tests/test_pet_summon_modes.py`

- [ ] **Step 1: Read the existing test for /pet/summon to copy its mock pattern**

```bash
cd backend && grep -l "pet/summon\|public_pet_summon" tests/ | head
```

Look for an existing fixture that mocks `pet_gateway.summon` — typically via `monkeypatch.setattr(pet_gateway, "summon", ...)`. Re-use that pattern.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_pet_summon_modes.py
import pytest

from app.services import pet_gateway


@pytest.fixture
def captured_calls(monkeypatch):
    calls: list[dict] = []

    async def _fake_summon(**kwargs):
        calls.append(kwargs)
        return ("ok", "zhipu")

    monkeypatch.setattr(pet_gateway, "summon", _fake_summon)
    return calls


async def test_greet_mode_when_no_post_no_selection(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "greet"
    assert "summoned you out of nowhere" in captured_calls[0]["system"]


async def test_summary_react_mode_with_post(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={"post_id": fake_post_id})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "summary_react"
    sys = captured_calls[0]["system"]
    assert "Pet Test" in sys      # title
    assert "devtools" in sys      # tag


async def test_selection_explain_when_explicit_flag(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "useEffect(() => fetch(url), [])",
        "mode": "selection_explain",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "selection_explain"
    assert "useEffect" in captured_calls[0]["system"]
    assert "Explain what it does" in captured_calls[0]["system"]


async def test_selection_qa_default_when_selection_no_mode(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "this is a paragraph",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "selection_qa"


async def test_mode_validation_rejects_garbage(client, captured_calls):
    r = await client.post("/api/pet/summon", json={"mode": "wat"})
    assert r.status_code == 422


async def test_disabled_article_context_forces_greet_mode(client, captured_calls,
                                                          fake_post_id):
    """When enable_article_context=False, ignore post_id/selection, force greet."""
    # Patch SiteMeta.pet_config to disable article context
    from sqlalchemy import update
    from app.db import AsyncSessionLocal
    from app.models import SiteMeta
    from app.schemas.pet import PetConfig
    cfg = PetConfig(enable_article_context=False)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg.model_dump()))
        await s.commit()
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "x",
    })
    body = r.json()
    assert body["mode"] == "greet"
    sys = captured_calls[0]["system"]
    assert "Pet Test" not in sys  # title NOT injected
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_summon_modes.py -v
```
Expected: failures — `mode` field missing from request body / response, etc.

- [ ] **Step 4: Replace `_build_prompt` and update the request handler in `pet.py`**

Replace `backend/app/routers/public/pet.py` content (everything except imports — keep them and add the new ones):

```python
"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, SiteMeta, Tag
from app.redis import get_redis
from app.schemas.pet import PetConfig, PetMode, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_assignment, pet_gateway, pet_prompt, rate_limit, secret_box
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

router = APIRouter()


class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=80)
    selection: str | None = Field(default=None, max_length=4000)
    mode: PetMode | None = None


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(
    request: Request,
    response: Response,
    s: AsyncSession = Depends(get_session),
) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    assigned = pet_assignment.verify_cookie(
        request.cookies.get(pet_assignment.COOKIE_NAME)
    )
    if assigned is None:
        assigned = pet_assignment.assign_species(
            ip=client_ip_from(request),
            user_agent=request.headers.get("user-agent"),
        )
        response.set_cookie(
            key=pet_assignment.COOKIE_NAME,
            value=pet_assignment.sign_cookie(assigned),
            max_age=pet_assignment.COOKIE_MAX_AGE,
            path="/",
            samesite="lax",
            httponly=False,
        )
    return PublicPetConfig(
        species=cfg.species,
        assigned_species=assigned,
        hat=cfg.hat, tint=cfg.tint,
        enabled=cfg.enabled, visitor_can_change=cfg.visitor_can_change,
    )


async def _resolve_secrets(s: AsyncSession, providers: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in providers:
        row = await integrations_svc.get(s, name=name)
        if row is None:
            continue
        out[name] = {
            "key": secret_box.decrypt(row.secret_encrypted),
            "model": (row.extra_json or {}).get("model"),
        }
    return out


@router.post("/pet/summon")
async def public_pet_summon(
    req: SummonRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    cfg = await _load_pet_config(s)
    ip_key = client_ip_key_part(request)

    breach = await rate_limit.check_pet(
        redis, ip=ip_key,
        per_ip_per_min=cfg.per_ip_per_min,
        per_ip_per_day=cfg.per_ip_per_day,
        global_per_day=cfg.global_per_day,
        unlimited=cfg.unlimited,
        hard_ceiling_per_day=cfg.hard_ceiling_per_day,
    )
    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned",
            actor=ip_hash(client_ip_from(request))[:12],
            meta={"source": "rate_limited", "breach": breach},
        )
        await s.commit()
        return {"quip": quip, "source": "rate_limited", "mode": "rate_limited"}

    # Determine mode and load post if relevant.
    if not cfg.enable_article_context:
        # Article context disabled — force greet, ignore post_id/selection.
        post_id = None
        selection = None
        mode: PetMode = "greet"
    else:
        post_id = req.post_id
        selection = req.selection
        mode = req.mode or pet_prompt.infer_mode(post_id=post_id, selection=selection)

    post: Post | None = None
    title: str | None = None
    tag_label: str | None = None
    summary: str | None = None
    if post_id:
        post = (await s.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
        if post is not None:
            title = post.title
            summary = post.summary
            if post.tag_id is not None:
                t = (await s.execute(select(Tag).where(Tag.id == post.tag_id))).scalar_one_or_none()
                tag_label = t.slug if t else None

    # Resolve assigned species (cookie → fingerprint).
    assigned = pet_assignment.verify_cookie(
        request.cookies.get(pet_assignment.COOKIE_NAME)
    ) or pet_assignment.assign_species(
        ip=client_ip_from(request),
        user_agent=request.headers.get("user-agent"),
    )

    system = pet_prompt.build_system(
        cfg, species=assigned, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
    )

    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        source = "fallback"
    else:
        secrets = await _resolve_secrets(s, cfg.providers)
        quip, source = await pet_gateway.summon(
            providers=cfg.providers,
            secrets=secrets,
            system=system,
            user="summon",
            fallback_lines=cfg.fallback_lines,
        )

    await write_event(
        s, type="pet.summoned",
        actor=ip_hash(client_ip_from(request))[:12],
        meta={"source": source, "mode": mode, "species": assigned},
    )
    await s.commit()
    return {"quip": quip, "source": source, "mode": mode}
```

Note: deleted the old `_build_prompt` function entirely (moved into `pet_prompt.build_system`).

- [ ] **Step 5: Run new tests + existing pet test files**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_summon_modes.py tests/test_public_pet.py -v
```
Expected: all pass. (If a stale `test_public_pet.py` test asserts the old return mode names like `"comment"` / `"explain"`, update it to the new mode names — they are now `summary_react` / `selection_qa` / `selection_explain`.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/public/pet.py backend/tests/test_pet_summon_modes.py
git commit -m "feat(pet): /pet/summon uses build_system + 4 modes + enable_article_context gate"
```

---

## Task 6: Admin /defaults + /reset endpoints

**Files:**
- Modify: `backend/app/routers/admin/pet.py`
- Test: `backend/tests/test_admin_pet_defaults.py`

- [ ] **Step 1: Read existing admin auth pattern**

```bash
cd backend && grep -l "current_admin\|admin_client" tests/test_admin*.py | head -3
```

Existing admin tests should have an `admin_client` fixture (logged-in HTTP client). Re-use it. If naming differs, copy the auth pattern from `tests/test_admin_pet.py`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_admin_pet_defaults.py
import pytest

from app.services.pet_assignment import SPECIES_BY_RARITY


@pytest.mark.usefixtures("seed_admin")  # rename to whatever fixture seeds the admin
async def test_get_defaults_returns_personas_and_templates(admin_client):
    r = await admin_client.get("/admin/pet/defaults")
    assert r.status_code == 200
    body = r.json()
    expected_species = {s for pool in SPECIES_BY_RARITY.values() for s in pool}
    assert set(body["personas"]) == expected_species
    assert set(body["mode_templates"]) == {
        "greet", "summary_react", "selection_explain", "selection_qa"
    }


async def test_reset_personas_section(admin_client):
    # First, mutate cat persona
    await admin_client.put("/admin/pet", json={
        **(await admin_client.get("/admin/pet")).json(),
        "personas": {**(await admin_client.get("/admin/pet")).json()["personas"], "cat": "MUT"},
    })
    cur = (await admin_client.get("/admin/pet")).json()
    assert cur["personas"]["cat"] == "MUT"
    # Reset only personas
    r = await admin_client.post("/admin/pet/reset?section=personas")
    assert r.status_code == 200
    after = r.json()
    assert after["personas"]["cat"] != "MUT"
    # Templates not touched
    cur_templates = cur["mode_templates"]
    assert after["mode_templates"] == cur_templates


async def test_reset_templates_section(admin_client):
    cur = (await admin_client.get("/admin/pet")).json()
    cur["mode_templates"]["greet"] = "MUT"
    await admin_client.put("/admin/pet", json=cur)
    after = (await admin_client.post("/admin/pet/reset?section=templates")).json()
    assert "MUT" not in after["mode_templates"]["greet"]


async def test_reset_both_section(admin_client):
    cur = (await admin_client.get("/admin/pet")).json()
    cur["personas"]["cat"] = "M1"
    cur["mode_templates"]["greet"] = "M2"
    await admin_client.put("/admin/pet", json=cur)
    after = (await admin_client.post("/admin/pet/reset?section=both")).json()
    assert "M1" not in after["personas"]["cat"]
    assert "M2" not in after["mode_templates"]["greet"]


async def test_reset_invalid_section_returns_422(admin_client):
    r = await admin_client.post("/admin/pet/reset?section=garbage")
    assert r.status_code == 422
```

If the admin client fixture is named differently, adapt accordingly — copy the pattern from `tests/test_admin_pet.py`.

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_defaults.py -v
```
Expected: 404 on `/admin/pet/defaults` and `/admin/pet/reset`.

- [ ] **Step 4: Add endpoints to `backend/app/routers/admin/pet.py`**

Replace file content with:

```python
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, SiteMeta
from app.schemas.pet import PetConfig, PetModeTemplates, PetPersonas

router = APIRouter()

ResetSection = Literal["personas", "templates", "both"]


@router.get("/pet", response_model=PetConfig)
async def get_pet(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.put("/pet", response_model=PetConfig, dependencies=[Depends(require_scope("write"))])
async def put_pet(
    req: PetConfig,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=req.model_dump())
    )
    await s.commit()
    return req


@router.get("/pet/defaults")
async def get_pet_defaults(
    _admin: Account = Depends(current_admin),
) -> dict:
    """Return schema defaults for personas + mode_templates so the frontend
    'Reset to defaults' button doesn't have to keep its own copy."""
    defaults = PetConfig()
    return {
        "personas": defaults.personas.model_dump(),
        "mode_templates": defaults.mode_templates.model_dump(),
    }


@router.post(
    "/pet/reset",
    response_model=PetConfig,
    dependencies=[Depends(require_scope("write"))],
)
async def reset_pet_section(
    section: ResetSection = Query(...),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    """Reset personas / templates / both back to schema defaults.
    Other PetConfig fields are preserved."""
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    cur = PetConfig(**{**PetConfig().model_dump(), **(site.pet_config or {})})
    payload = cur.model_dump()
    if section in ("personas", "both"):
        payload["personas"] = PetPersonas().model_dump()
    if section in ("templates", "both"):
        payload["mode_templates"] = PetModeTemplates().model_dump()
    new = PetConfig(**payload)
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=new.model_dump())
    )
    await s.commit()
    return new
```

- [ ] **Step 5: Run tests**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_defaults.py tests/test_admin_pet.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/admin/pet.py backend/tests/test_admin_pet_defaults.py
git commit -m "feat(pet): admin /pet/defaults + /pet/reset endpoints"
```

---

## Task 7: Frontend api/pet.js helpers

**Files:**
- Modify: `src/api/pet.js`

- [ ] **Step 1: Read the current api/pet.js to match patterns**

```bash
cat src/api/pet.js
```

Identify the existing `apiPet.get`/`apiPet.put` style (likely a fetch wrapper with auth header). Re-use it.

- [ ] **Step 2: Add `fetchDefaults` and `resetSection` helpers**

Edit `src/api/pet.js` to add these two methods to the `apiPet` export. Example shape (adapt to your wrapper's idiom):

```js
async function fetchDefaults() {
  return await adminGet('/admin/pet/defaults');
}

async function resetSection(section /* 'personas' | 'templates' | 'both' */) {
  return await adminPost(`/admin/pet/reset?section=${encodeURIComponent(section)}`);
}

export const apiPet = { ...existing, fetchDefaults, resetSection };
```

If `adminPost` doesn't exist for query-string POSTs, copy the existing `adminPut` and adapt it.

- [ ] **Step 3: Smoke test in the browser console (optional but recommended)**

After saving, open `/admin/pet`, then in DevTools console:

```js
const r = await fetch('/api/admin/pet/defaults', { credentials: 'include' });
console.log(Object.keys((await r.json()).personas).length);  // expect 27
```

- [ ] **Step 4: Commit**

```bash
git add src/api/pet.js
git commit -m "feat(pet): admin api helpers for defaults + reset"
```

---

## Task 8: Frontend AsciiPet — detectMode + send mode

**Files:**
- Modify: `src/components/AsciiPet.jsx`
- Test: `src/components/AsciiPet.test.jsx` (create or extend)

- [ ] **Step 1: Locate the summon call**

```bash
grep -n "/api/pet/summon\|summon" src/components/AsciiPet.jsx
```

This is the fetch you'll modify to include `mode`.

- [ ] **Step 2: Write the failing unit test**

```jsx
// src/components/AsciiPet.test.jsx — add (or create) these tests
import { describe, it, expect } from 'vitest';
import { detectMode } from './AsciiPet.jsx';

describe('detectMode', () => {
  it('returns greet when not on an article', () => {
    expect(detectMode({ inArticle: false, selection: '' })).toBe('greet');
  });

  it('returns summary_react when on article with no selection', () => {
    expect(detectMode({ inArticle: true, selection: '' })).toBe('summary_react');
  });

  it('returns selection_qa for prose selection', () => {
    document.body.innerHTML = '<p id="t">hello world</p>';
    const range = document.createRange();
    range.selectNodeContents(document.getElementById('t'));
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    expect(detectMode({ inArticle: true, selection: 'hello' })).toBe('selection_qa');
  });

  it('returns selection_explain for code selection inside <pre>', () => {
    document.body.innerHTML = '<pre id="c"><code>const x = 1</code></pre>';
    const range = document.createRange();
    range.selectNodeContents(document.querySelector('#c code'));
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    expect(detectMode({ inArticle: true, selection: 'const x = 1' })).toBe('selection_explain');
  });
});
```

- [ ] **Step 3: Run test to verify failure**

```bash
npx vitest run src/components/AsciiPet.test.jsx
```
Expected: failure — `detectMode` not exported.

- [ ] **Step 4: Add `detectMode` to `AsciiPet.jsx` and use it in the summon call**

Add to `src/components/AsciiPet.jsx` (export the function so tests can import it):

```jsx
export function detectMode({ inArticle, selection }) {
  if (!inArticle) return 'greet';
  if (!selection) return 'summary_react';
  const sel = typeof window !== 'undefined' ? window.getSelection() : null;
  if (!sel || sel.rangeCount === 0) return 'selection_qa';
  const ancestor = sel.getRangeAt(0).commonAncestorContainer;
  const inCode = ancestor.nodeType === 1
    ? ancestor.closest('pre, code') !== null
    : ancestor.parentElement?.closest('pre, code') !== null;
  return inCode ? 'selection_explain' : 'selection_qa';
}
```

In the summon handler — find the line that does `fetch('/api/pet/summon', { method: 'POST', body: JSON.stringify({ post_id, selection }) })` and update it:

```jsx
const mode = detectMode({ inArticle: !!postId, selection });
const r = await fetch('/api/pet/summon', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ post_id: postId, selection, mode }),
});
```

(Adapt variable names — `postId`/`post_id`/`selection` — to what's already in the file.)

- [ ] **Step 5: Run all frontend tests**

```bash
npx vitest run
```
Expected: all pass.

- [ ] **Step 6: Manual browser test (golden path)**

Start dev: `npm run dev` (proxy → backend on :51820, which must be running). Then:
1. Open `/` (no article) → click pet → expect a generic greet line.
2. Open `/p/<some-post-id>` → click pet → expect a line referencing the article.
3. Select a sentence in the article body → click pet → expect a "qa" style response.
4. Select code inside a `<pre><code>` block → click pet → expect a "code explain" style response.

Confirm in DevTools Network tab that the request body contains the expected `mode` for each scenario.

- [ ] **Step 7: Commit**

```bash
git add src/components/AsciiPet.jsx src/components/AsciiPet.test.jsx
git commit -m "feat(pet): AsciiPet sends mode based on selection context"
```

---

## Task 9: Admin Pet page — 3 tabs

**Files:**
- Modify: `src/admin/Pet.jsx` (374-line refactor)

- [ ] **Step 1: Read the current Pet.jsx to understand state shape**

```bash
wc -l src/admin/Pet.jsx
sed -n '1,80p' src/admin/Pet.jsx
```

The current file is a single form. Strategy: split into three subcomponents (`<Behavior>`, `<Personas>`, `<Templates>`) sharing `config` state via props, with a parent that owns the state, the API call, and the tab router.

- [ ] **Step 2: Create the new Pet.jsx structure**

Rewrite `src/admin/Pet.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiPet } from '../api/pet.js';

import PetBehavior from './pet/PetBehavior.jsx';
import PetPersonas from './pet/PetPersonas.jsx';
import PetTemplates from './pet/PetTemplates.jsx';

const TABS = [
  { id: 'behavior', label: 'Behavior' },
  { id: 'personas', label: 'Personas' },
  { id: 'templates', label: 'Prompt templates' },
];

export default function Pet() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'behavior';

  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedTick, setSavedTick] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiPet.get()
      .then((res) => mounted && (setConfig(res), setError(null)))
      .catch((err) => mounted && setError(err?.detail || err?.message || 'failed to load'))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  function patch(partial) {
    setConfig((prev) => ({ ...prev, ...partial }));
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    try {
      const next = await apiPet.put(config);
      setConfig(next);
      setSavedTick((t) => t + 1);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  async function resetSection(section) {
    if (!confirm(`Reset all ${section} to defaults? This cannot be undone.`)) return;
    setSaving(true);
    try {
      const next = await apiPet.resetSection(section);
      setConfig(next);
      setSavedTick((t) => t + 1);
    } catch (e) {
      setError(e?.detail || e?.message || 'reset failed');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="pad">loading…</div>;
  if (error) return <div className="pad err">{error}</div>;
  if (!config) return null;

  return (
    <div className="admin-pet">
      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setParams({ tab: t.id })}
          >{t.label}</button>
        ))}
        <span className="grow" />
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? 'saving…' : 'Save'}
        </button>
        {savedTick > 0 && <span className="saved-hint">✓ saved</span>}
      </nav>

      {tab === 'behavior' && <PetBehavior config={config} patch={patch} />}
      {tab === 'personas' && (
        <PetPersonas config={config} patch={patch} onReset={() => resetSection('personas')} />
      )}
      {tab === 'templates' && (
        <PetTemplates config={config} patch={patch} onReset={() => resetSection('templates')} />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `src/admin/pet/PetBehavior.jsx`**

```jsx
const PRESETS = {
  strict:    { per_ip_per_min: 6,  per_ip_per_day: 30,   global_per_day: 500,  unlimited: false },
  relaxed:   { per_ip_per_min: 30, per_ip_per_day: 500,  global_per_day: 5000, unlimited: false },
  unlimited: { per_ip_per_min: 30, per_ip_per_day: 500,  global_per_day: 5000, unlimited: true  },
};

function detectPreset(config) {
  for (const [name, p] of Object.entries(PRESETS)) {
    if (
      config.per_ip_per_min === p.per_ip_per_min
      && config.per_ip_per_day === p.per_ip_per_day
      && config.global_per_day === p.global_per_day
      && !!config.unlimited === p.unlimited
    ) return name;
  }
  return 'custom';
}

export default function PetBehavior({ config, patch }) {
  const preset = detectPreset(config);
  return (
    <div className="form pad">
      <label>
        <input type="checkbox" checked={config.enabled}
               onChange={(e) => patch({ enabled: e.target.checked })} />
        Enabled
      </label>
      <label>
        <input type="checkbox" checked={config.visitor_can_change}
               onChange={(e) => patch({ visitor_can_change: e.target.checked })} />
        Visitor can change species
      </label>
      <label>
        <input type="checkbox" checked={config.enable_article_context}
               onChange={(e) => patch({ enable_article_context: e.target.checked })} />
        Article context awareness
      </label>

      <fieldset>
        <legend>Providers (fallback chain)</legend>
        <input type="text" value={(config.providers || []).join(', ')}
               onChange={(e) => patch({
                 providers: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
               })}
               placeholder="zhipu, qwen, doubao, deepseek, anthropic" />
      </fieldset>

      <fieldset>
        <legend>Rate limit</legend>
        {['strict','relaxed','unlimited'].map((p) => (
          <label key={p}>
            <input type="radio" name="preset" checked={preset === p}
                   onChange={() => patch(PRESETS[p])} />
            {p}
          </label>
        ))}
        {preset === 'custom' && <span className="hint">(custom)</span>}
        <details>
          <summary>Advanced</summary>
          <label>per_ip_per_min: <input type="number" min="1" max="120"
            value={config.per_ip_per_min}
            onChange={(e) => patch({ per_ip_per_min: Number(e.target.value) })} /></label>
          <label>per_ip_per_day: <input type="number" min="1" max="10000"
            value={config.per_ip_per_day}
            onChange={(e) => patch({ per_ip_per_day: Number(e.target.value) })} /></label>
          <label>global_per_day: <input type="number" min="10" max="100000"
            value={config.global_per_day}
            onChange={(e) => patch({ global_per_day: Number(e.target.value) })} /></label>
          <label>hard_ceiling_per_day: <input type="number" min="100" max="100000"
            value={config.hard_ceiling_per_day}
            onChange={(e) => patch({ hard_ceiling_per_day: Number(e.target.value) })} /></label>
          <label>
            <input type="checkbox" checked={!!config.unlimited}
                   onChange={(e) => patch({ unlimited: e.target.checked })} />
            unlimited (skip 3-layer, only enforce hard_ceiling)
          </label>
        </details>
      </fieldset>

      <fieldset>
        <legend>Fallback lines (one per line)</legend>
        <textarea rows={4}
          value={(config.fallback_lines || []).join('\n')}
          onChange={(e) => patch({
            fallback_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>

      <fieldset>
        <legend>Tired lines (rate-limited reply)</legend>
        <textarea rows={4}
          value={(config.tired_lines || []).join('\n')}
          onChange={(e) => patch({
            tired_lines: e.target.value.split('\n').filter((l) => l.trim()),
          })} />
      </fieldset>
    </div>
  );
}
```

- [ ] **Step 4: Create `src/admin/pet/PetPersonas.jsx`**

```jsx
const SPECIES_BY_RARITY = {
  common:    ['duck', 'goose', 'blob', 'cat', 'rabbit'],
  uncommon:  ['penguin', 'owl', 'turtle', 'capybara'],
  rare:      ['mushroom', 'ghost', 'snail', 'cactus', 'chonk'],
  epic:      ['octopus', 'jellyfish', 'axolotl', 'robot'],
  legendary: ['dragon', 'phoenix', 'fox', 'shiba', 'mochi',
              'panda', 'hamster', 'bee', 'otter'],
};

const RARITY_COLOR = {
  common: '#9aa6b3', uncommon: '#7dbf8e', rare: '#5c9ddc',
  epic: '#b89cf0', legendary: '#f5b44c',
};

export default function PetPersonas({ config, patch, onReset }) {
  const personas = config.personas || {};
  function setPersona(species, value) {
    patch({ personas: { ...personas, [species]: value } });
  }
  return (
    <div className="form pad">
      <p className="hint">
        Each species speaks in its own voice. The persona text is injected
        into the system prompt before every reply.
      </p>
      <div>
        {Object.entries(SPECIES_BY_RARITY).map(([rarity, species]) => (
          <details key={rarity} open={rarity === 'common'}>
            <summary>
              <span className="rarity-dot" style={{ background: RARITY_COLOR[rarity] }} />
              {rarity} ({species.length})
            </summary>
            {species.map((s) => (
              <div className="persona-row" key={s}>
                <label className="species-label">{s}</label>
                <textarea rows={3} maxLength={400}
                  value={personas[s] || ''}
                  onChange={(e) => setPersona(s, e.target.value)} />
              </div>
            ))}
          </details>
        ))}
      </div>
      <button type="button" onClick={onReset} className="danger">
        Reset all personas to defaults
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Create `src/admin/pet/PetTemplates.jsx`**

```jsx
const MODES = [
  { id: 'greet', label: 'greet — visitor summoned with no article context' },
  { id: 'summary_react', label: 'summary_react — visitor on article, no selection' },
  { id: 'selection_explain', label: 'selection_explain — selected code/snippet' },
  { id: 'selection_qa', label: 'selection_qa — selected prose' },
];

export default function PetTemplates({ config, patch, onReset }) {
  const tpl = config.mode_templates || {};
  function setTpl(mode, value) {
    patch({ mode_templates: { ...tpl, [mode]: value } });
  }
  return (
    <div className="form pad">
      <p className="hint">
        Available placeholders in templates:
        {' '}<code>{'{title}'}</code> <code>{'{tag}'}</code>
        {' '}<code>{'{summary}'}</code> <code>{'{selection}'}</code>.
        The persona is auto-prepended; <code>{'{persona}'}</code> in templates
        is left literal.
      </p>
      {MODES.map((m) => (
        <fieldset key={m.id}>
          <legend>{m.label}</legend>
          <textarea rows={6} maxLength={800}
            value={tpl[m.id] || ''}
            onChange={(e) => setTpl(m.id, e.target.value)}
            style={{ fontFamily: 'monospace' }} />
        </fieldset>
      ))}
      <button type="button" onClick={onReset} className="danger">
        Reset all templates to defaults
      </button>
    </div>
  );
}
```

- [ ] **Step 6: Smoke-check the page renders**

```bash
npm run dev
# open http://localhost:5173/admin/pet
# click each tab; URL should change to ?tab=personas etc.
# expand 'common' rarity group; edit cat persona; switch to templates and back — edit must persist (state lives in parent)
# click "Save"; success hint shows.
# click "Reset all personas to defaults" — confirm dialog → click OK → cat persona reverts.
```

- [ ] **Step 7: Run frontend test suite**

```bash
npx vitest run
```
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/admin/Pet.jsx src/admin/pet/
git commit -m "feat(pet): admin Pet page split into Behavior/Personas/Templates tabs"
```

---

## Task 10: End-to-end smoke + cross-check

**Files:**
- None new. Final verification + integration test.

- [ ] **Step 1: Start backend + frontend**

```bash
# terminal 1
cd backend && set -a && source .env && set +a && uv run uvicorn app.main:app --port 51820 --reload

# terminal 2
npm run dev
```

- [ ] **Step 2: Verify each mode end-to-end in the browser**

Navigate to `http://localhost:5173`:

1. **greet** — On `/`, click pet. Tooltip / quip should sound like the assigned species' voice (open DevTools Network tab → check the request payload includes `mode: "greet"`).
2. **summary_react** — Open any post `/p/<id>`, click pet without selecting anything. Quip should reference the article.
3. **selection_explain** — Inside a `<pre><code>` block in the post, select a few tokens, click pet. Quip should sound like it's explaining the snippet.
4. **selection_qa** — Select a non-code paragraph, click pet. Quip should sound conversational about the passage.

In each case, confirm the request body in Network tab has the right `mode`.

- [ ] **Step 3: Verify unlimited toggle**

In `/admin/pet?tab=behavior`, click the **Unlimited** preset → Save. Check `/api/admin/pet` returns `unlimited: true`. Spam-click the pet 50 times — none should hit a rate-limit fallback (you'd see `pets 累了` style replies). Check daily counter via Redis CLI in the dev container if curious:

```bash
docker compose -f docker-compose.dev.yml exec redis redis-cli get rl:pet:ceiling:$(date -u +%Y%m%d)
```

- [ ] **Step 4: Verify reset endpoints**

In `/admin/pet?tab=personas`, edit the `cat` persona → save → click "Reset all personas to defaults" → confirm dialog → cat persona reverts. Repeat for templates tab.

- [ ] **Step 5: Run the full backend test suite**

```bash
cd backend && set -a && source .env.test && set +a && uv run pytest -q
```
Expected: all pass.

- [ ] **Step 6: Run the full frontend test suite**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run
```
Expected: all pass.

- [ ] **Step 7: Final commit (if anything still uncommitted) and push the branch**

```bash
git status
# if dirty, commit any remaining whitespace / format fixups
git push -u origin <feature-branch-name>
```

- [ ] **Step 8: Open PR**

```bash
gh pr create --title "feat(pet): personality system — 27 personas + 4 modes + unlimited" \
  --body "$(cat <<'EOF'
## Summary
- 27 per-species personas (admin-editable; defaults shipped)
- 4 prompt modes (greet / summary_react / selection_explain / selection_qa) with admin-editable templates
- Frontend marks selection mode by inspecting `<pre>/<code>` ancestors
- `unlimited` rate-limit toggle + `hard_ceiling_per_day` fallback
- Admin Pet page split into 3 tabs (Behavior / Personas / Templates) with `?tab=` query persistence
- `/admin/pet/defaults` (GET) and `/admin/pet/reset` (POST) endpoints

Spec: `docs/superpowers/specs/2026-05-01-pet-personality-system-design.md`

## Test plan
- [x] Backend pytest suite passes
- [x] Frontend vitest suite passes
- [x] Manual: 4 modes verified in browser; unlimited toggle works; reset endpoints work

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes for the implementer

- **Branch strategy**: create `feat/pet-personality` off `main` before starting Task 1.
- **Don't forget the test DB**: every backend test command in this plan assumes you've sourced `.env.test`. The repo's `tests/conftest.py` will refuse to run otherwise.
- **API path prefix**: in browser fetches use `/api/...`; in pytest httpx client use `/api/...` as well (the AsyncClient is configured against the FastAPI app mounted at `/api`).
- **No alembic migration**: `pet_config` is a JSONB column on `site_meta`. New fields are loaded via the `{**defaults, **raw}` merge in `_load_pet_config` / `get_pet`.
