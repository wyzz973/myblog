# Pet Multi-LLM Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade pet so it (1) talks via a multi-provider LLM gateway (智谱 / 通义千问 / 豆包 + Anthropic fallback), (2) gives article-aware replies and explains selected text, (3) is rate-limited in three layers to cap token spend, and (4) ships 22 ASCII species (18 imported from `dead1786/buddy-skin-editor` + 4 legendary hand-authored).

**Architecture:** Provider adapters implement a single `chat()` Protocol; a `pet_gateway.summon()` orchestrator tries them in order and falls back to canned lines on full failure. Existing `Integration` table holds one encrypted secret per provider. Frontend `AsciiPet` posts `{mode, post_id?, selection?}` to a refactored `/api/pet/summon`; `Reader` shows a "click pet to explain" hint when a selection is alive.

**Tech Stack:** FastAPI 0.115, async SQLAlchemy 2.0, Pydantic v2, Redis, Alembic; React 18, Vite 5, vitest; Anthropic SDK (existing) + `httpx` for OpenAI-compatible providers.

**Spec:** `docs/superpowers/specs/2026-05-01-pet-multi-llm-gateway-design.md`

> **Migration numbering correction:** spec said `0008` but the next free slot is `0010` — `0008_event_log_archive.py` and `0009_drop_avatar_path.py` already exist. Use `0010` throughout.

---

## File Map

**Backend — new:**
- `backend/alembic/versions/0010_pet_multi_provider.py`
- `backend/app/services/pet_adapters/__init__.py`
- `backend/app/services/pet_adapters/anthropic.py` (refactor of existing `pet_llm.py`)
- `backend/app/services/pet_adapters/openai_compat.py`
- `backend/app/services/pet_gateway.py`
- `backend/tests/test_alembic_0010_roundtrip.py`
- `backend/tests/test_pet_adapter_anthropic.py`
- `backend/tests/test_pet_adapter_openai_compat.py`
- `backend/tests/test_pet_gateway.py`
- `backend/tests/test_pet_rate_limit.py`

**Backend — modify:**
- `backend/app/models/integration.py` — relax CheckConstraint
- `backend/app/services/integrations.py` — expand Literal, expand `upsert(name=...)`
- `backend/app/services/rate_limit.py` — add `check_pet()` 3-layer helper
- `backend/app/schemas/pet.py` — extend `PetConfig`
- `backend/app/schemas/integration.py` — add `Zhipu/Qwen/Doubao IntegrationGet/Put`
- `backend/app/routers/public/pet.py` — payload schema, mode routing, prompt builder, gateway call
- `backend/app/routers/admin/integrations.py` — three new GET/PUT pairs
- `backend/tests/test_pet_summon.py` — extend for new payloads
- `backend/tests/test_admin_integrations.py` — extend for new providers
- `backend/app/services/pet_llm.py` — delete (logic moves to adapters/anthropic.py)

**Frontend — new:**
- `src/components/pet/species.js` — 22 species data
- `src/components/pet/__tests__/payload.test.js`
- `src/components/pet/__tests__/species.test.js`

**Frontend — modify:**
- `src/components/AsciiPet.jsx` — drop `BODY` dict + `{L}{R}{M}`; consume `species.js`; state→eye-char map; payload-aware click; rarity-grouped panel; localStorage migration
- `src/components/Reader.jsx` — `selectionchange` listener; lift hint via prop drilled from App
- `src/App.jsx` — `petHint` state + pass to AsciiPet
- `src/styles.css` — rarity styling for chips (gold border for legendary)

---

## Provider Reference

```python
PROVIDER_REGISTRY = {
    "zhipu": {
        "adapter": "openai_compat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "adapter": "openai_compat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "doubao": {
        "adapter": "openai_compat",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": None,  # must be set per-account in extra_json["model"] (endpoint id)
    },
    "anthropic": {
        "adapter": "anthropic",
        "default_model": "claude-haiku-4-5-20251001",
    },
}
```

All three Chinese providers expose an OpenAI-compatible `POST {base_url}/chat/completions` with `Authorization: Bearer <key>`, request body `{model, messages, max_tokens, temperature}`, response `{choices: [{message: {content}}]}`. One adapter handles all three. Verify exact URLs against current docs at impl time (Task 0).

---

## Task 0: Verify provider endpoints (10-15 min spike)

**Files:** none (research only)

- [ ] **Step 1:** Confirm 智谱 docs: `https://open.bigmodel.cn/dev/api/normal-model/glm-4` — verify `chat/completions` URL, `glm-4-flash` model id, bearer auth format.
- [ ] **Step 2:** Confirm 通义千问 OpenAI-compat docs: `https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope` — verify base url + `qwen-turbo` model id.
- [ ] **Step 3:** Confirm 豆包 (火山方舟) docs: `https://www.volcengine.com/docs/82379/1099475` — verify base url + that `model` is the endpoint id (`ep-...`).
- [ ] **Step 4:** If any URL/model differs from `PROVIDER_REGISTRY` above, update this plan inline and proceed.

> Use context7 MCP if available: `mcp__plugin_context7_context7__resolve-library-id` with library names like "zhipuai" / "dashscope" / "volcengine ark".

---

## Task 1: Alembic 0010 — relax integrations CHECK

**Files:**
- Create: `backend/alembic/versions/0010_pet_multi_provider.py`
- Test: `backend/tests/test_alembic_0010_roundtrip.py`

- [ ] **Step 1: Write the failing round-trip test**

```python
"""Round-trip alembic to 0009 and back to 0010."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_0010_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0009_drop_avatar_path")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"
    cur = _alembic("current")
    assert "0009_drop_avatar_path" in cur.stdout

    up = _alembic("upgrade", "0010_pet_multi_provider")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"
    cur = _alembic("current")
    assert "0010_pet_multi_provider" in cur.stdout

    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && uv run pytest tests/test_alembic_0010_roundtrip.py -v
```
Expected: FAIL — no migration `0010_pet_multi_provider` yet.

- [ ] **Step 3: Write the migration**

```python
"""pet multi provider — relax integrations.name CHECK

Revision ID: 0010_pet_multi_provider
Revises: 0009_drop_avatar_path
Create Date: 2026-05-01
"""
from alembic import op

revision = "0010_pet_multi_provider"
down_revision = "0009_drop_avatar_path"
branch_labels = None
depends_on = None

NEW = "name IN ('github','anthropic','zhipu','qwen','doubao')"
OLD = "name IN ('github','anthropic')"


def upgrade() -> None:
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", NEW)


def downgrade() -> None:
    # Refuse downgrade if rows exist for new providers — would orphan them.
    op.execute(
        "DELETE FROM integrations WHERE name IN ('zhipu','qwen','doubao')"
    )
    op.drop_constraint("ck_integrations_name", "integrations", type_="check")
    op.create_check_constraint("ck_integrations_name", "integrations", OLD)
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && uv run pytest tests/test_alembic_0010_roundtrip.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0010_pet_multi_provider.py backend/tests/test_alembic_0010_roundtrip.py
git commit -m "feat(pet): alembic 0010 — relax integrations CHECK for zhipu/qwen/doubao"
```

---

## Task 2: Update Integration model + integrations service

**Files:**
- Modify: `backend/app/models/integration.py`
- Modify: `backend/app/services/integrations.py`
- Test: `backend/tests/test_integrations_service.py`

- [ ] **Step 1: Write a failing test for the new providers**

Append to `backend/tests/test_integrations_service.py`:

```python
async def test_upsert_accepts_zhipu(s):
    row = await integrations_svc.upsert(
        s, name="zhipu", username=None, secret="zhipu-key-1",
        extra={"model": "glm-4-flash"},
    )
    assert row.name == "zhipu"
    assert row.extra_json["model"] == "glm-4-flash"


async def test_upsert_accepts_qwen_and_doubao(s):
    await integrations_svc.upsert(s, name="qwen", username=None, secret="qwen-key")
    await integrations_svc.upsert(s, name="doubao", username=None, secret="doubao-key", extra={"model": "ep-test"})
    z = await integrations_svc.get(s, name="qwen")
    d = await integrations_svc.get(s, name="doubao")
    assert z is not None and d is not None
```

- [ ] **Step 2: Run — expect FAIL** on `Literal` type narrowing or DB CHECK violation.

```
cd backend && uv run pytest tests/test_integrations_service.py -v
```

- [ ] **Step 3: Update `Integration` model**

In `backend/app/models/integration.py` change the CheckConstraint:

```python
__table_args__ = (
    CheckConstraint(
        "name IN ('github','anthropic','zhipu','qwen','doubao')",
        name="ck_integrations_name",
    ),
)
```

- [ ] **Step 4: Update `integrations_svc.upsert`**

In `backend/app/services/integrations.py`:

```python
from typing import Literal

ProviderName = Literal["github", "anthropic", "zhipu", "qwen", "doubao"]

async def upsert(
    s: AsyncSession,
    *,
    name: ProviderName,
    username: str | None = None,
    secret: str,
    extra: dict[str, Any] | None = None,
) -> Integration:
    ...
```

- [ ] **Step 5: Run tests to verify pass**

```
cd backend && uv run pytest tests/test_integrations_service.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/integration.py backend/app/services/integrations.py backend/tests/test_integrations_service.py
git commit -m "feat(pet): integrations service accepts zhipu/qwen/doubao"
```

---

## Task 3: Extend PetConfig schema

**Files:**
- Modify: `backend/app/schemas/pet.py`
- Modify: `backend/tests/test_admin_pet.py`

- [ ] **Step 1: Write failing tests for new fields**

Append to `backend/tests/test_admin_pet.py`:

```python
async def test_petconfig_defaults_include_new_fields(client, admin_headers):
    r = await client.get("/api/admin/pet", headers=admin_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["providers"] == ["zhipu"]
    assert j["per_ip_per_min"] == 6
    assert j["per_ip_per_day"] == 30
    assert j["global_per_day"] == 500
    assert j["max_context_chars"] == 500
    assert j["enable_article_context"] is True
    assert isinstance(j["tired_lines"], list) and len(j["tired_lines"]) >= 1


async def test_petconfig_rejects_unknown_provider(client, admin_headers):
    body = {
        "providers": ["openai"],  # not in registry
        "fallback_lines": ["x"],
        "tired_lines": ["y"],
    }
    r = await client.put("/api/admin/pet", headers=admin_headers, json=body)
    assert r.status_code == 422
```

- [ ] **Step 2: Run — expect FAIL.**

```
cd backend && uv run pytest tests/test_admin_pet.py -v
```

- [ ] **Step 3: Extend `PetConfig`**

Replace the class in `backend/app/schemas/pet.py`:

```python
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
```

> Note: the old `rate_limit_per_min` field is dropped. Existing rows in `site_meta.pet_config` JSONB that still carry it will simply lose that key on next admin save (the public loader merges defaults; no crash). The old `model` field is also dropped — model selection now lives in each provider's `Integration.extra_json["model"]`.

- [ ] **Step 4: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_admin_pet.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/pet.py backend/tests/test_admin_pet.py
git commit -m "feat(pet): extend PetConfig with providers/3-layer rate limits/tired_lines"
```

---

## Task 4: Refactor pet_llm.py → adapters/anthropic.py

**Files:**
- Create: `backend/app/services/pet_adapters/__init__.py` (empty)
- Create: `backend/app/services/pet_adapters/anthropic.py`
- Delete: `backend/app/services/pet_llm.py`
- Create: `backend/tests/test_pet_adapter_anthropic.py`
- Modify: `backend/tests/test_pet_summon.py` (re-target import)
- Modify: `backend/app/routers/admin/integrations.py` (re-target import)

- [ ] **Step 1: Write failing adapter test**

Create `backend/tests/test_pet_adapter_anthropic.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.services.pet_adapters import anthropic as adapter

pytestmark = pytest.mark.asyncio


async def test_chat_returns_text_on_success():
    fake_msg = AsyncMock()
    fake_msg.content = [AsyncMock(text="hi human")]
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=fake_msg)
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        text = await adapter.chat(
            api_key="sk-test",
            model="claude-haiku-4-5-20251001",
            system="be brief",
            user="hello",
            max_tokens=80,
            temperature=0.9,
            timeout=5.0,
        )
        assert text == "hi human"


async def test_chat_raises_on_failure():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("api down")):
        with pytest.raises(Exception):
            await adapter.chat(
                api_key="sk-test",
                model="claude-haiku-4-5-20251001",
                system="x", user="y",
            )


async def test_ping_with_valid_key():
    fake = AsyncMock()
    fake.messages.create = AsyncMock(return_value=AsyncMock())
    with patch("anthropic.AsyncAnthropic", return_value=fake):
        assert await adapter.ping("sk-test", "claude-haiku-4-5-20251001") is True


async def test_ping_with_bad_key():
    with patch("anthropic.AsyncAnthropic", side_effect=Exception("auth")):
        assert await adapter.ping("sk-bad", "claude-haiku-4-5-20251001") is False
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

```
cd backend && uv run pytest tests/test_pet_adapter_anthropic.py -v
```

- [ ] **Step 3: Create the adapter**

`backend/app/services/pet_adapters/__init__.py`: (empty file)

`backend/app/services/pet_adapters/anthropic.py`:

```python
"""Anthropic adapter for the pet gateway."""
from __future__ import annotations

import anthropic
import structlog

log = structlog.get_logger(__name__)


async def chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 80,
    temperature: float = 0.9,
    timeout: float = 5.0,
) -> str:
    """Single chat call. Raises on failure (caller handles fallback)."""
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text if msg.content else ""
    if not text.strip():
        raise RuntimeError("anthropic returned empty content")
    return text.strip()


async def ping(api_key: str, model: str) -> bool:
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=5.0)
        await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("anthropic.ping_failed", model=model, error=repr(e))
        return False
```

- [ ] **Step 4: Update import sites**

In `backend/app/routers/admin/integrations.py` — replace `from app.services import pet_llm as pet_svc` with `from app.services.pet_adapters import anthropic as anthropic_adapter`. Update `pet_svc.ping(req.token, model)` calls accordingly. Verify all callsites compile.

In `backend/tests/test_pet_summon.py` — replace `from app.services import pet_llm` with `from app.services.pet_adapters import anthropic as anthropic_adapter`. Update test bodies (`pet_llm.ping` → `anthropic_adapter.ping`, `pet_llm.summon` → temporarily skip — `summon` lives in pet_gateway in Task 6; mark these tests xfail with comment "moves to test_pet_gateway in Task 6").

- [ ] **Step 5: Delete old file**

```
rm backend/app/services/pet_llm.py
```

- [ ] **Step 6: Run all backend tests — verify nothing else broke**

```
cd backend && uv run pytest tests/test_pet_adapter_anthropic.py tests/test_admin_integrations.py -v
```
Expected: PASS for adapter test; admin integrations may have minor compile-fix needs.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/pet_adapters/ backend/tests/test_pet_adapter_anthropic.py backend/app/routers/admin/integrations.py backend/tests/test_pet_summon.py
git rm backend/app/services/pet_llm.py
git commit -m "refactor(pet): pet_llm.py -> pet_adapters/anthropic.py"
```

---

## Task 5: OpenAI-compatible adapter

**Files:**
- Create: `backend/app/services/pet_adapters/openai_compat.py`
- Create: `backend/tests/test_pet_adapter_openai_compat.py`

- [ ] **Step 1: Write failing test using `httpx.MockTransport`**

```python
import httpx
import pytest

from app.services.pet_adapters import openai_compat as adapter

pytestmark = pytest.mark.asyncio


def _ok_handler(content: str = "你好"):
    async def _h(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [{"message": {"content": content}}],
        }
        return httpx.Response(200, json=body)
    return _h


def _fail_handler(status: int):
    async def _h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "boom"})
    return _h


async def test_chat_parses_openai_response():
    transport = httpx.MockTransport(_ok_handler("compiling..."))
    text = await adapter.chat(
        api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
        transport=transport,
    )
    assert text == "compiling..."


async def test_chat_sends_bearer_auth_and_correct_body():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    await adapter.chat(
        api_key="abc", base_url="https://example/v1", model="m1",
        system="sys", user="usr", max_tokens=80, temperature=0.5,
        transport=httpx.MockTransport(handler),
    )
    assert captured["auth"] == "Bearer abc"
    assert captured["url"] == "https://example/v1/chat/completions"
    assert '"model":"m1"' in captured["json"]
    assert '"max_tokens":80' in captured["json"]


async def test_chat_raises_on_4xx():
    transport = httpx.MockTransport(_fail_handler(401))
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=transport,
        )


async def test_chat_raises_on_5xx():
    transport = httpx.MockTransport(_fail_handler(500))
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=transport,
        )


async def test_chat_raises_on_empty_content():
    async def h(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
    with pytest.raises(adapter.OpenAICompatError):
        await adapter.chat(
            api_key="k", base_url="https://x/v1", model="m", system="s", user="u",
            transport=httpx.MockTransport(h),
        )
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

```
cd backend && uv run pytest tests/test_pet_adapter_openai_compat.py -v
```

- [ ] **Step 3: Implement adapter**

`backend/app/services/pet_adapters/openai_compat.py`:

```python
"""Generic OpenAI-compatible chat adapter (zhipu, qwen, doubao, ...)."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class OpenAICompatError(RuntimeError):
    """Raised when an OpenAI-compatible provider call fails or returns empty."""


async def chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 80,
    temperature: float = 0.9,
    timeout: float = 5.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Call POST {base_url}/chat/completions and return the first choice's text.

    `transport` parameter is for tests (httpx.MockTransport).
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        try:
            r = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as e:
            log.warning("openai_compat.transport_error", url=url, error=repr(e))
            raise OpenAICompatError(f"transport: {e}") from e
        if r.status_code >= 400:
            log.warning("openai_compat.http_error", url=url, status=r.status_code, body=r.text[:200])
            raise OpenAICompatError(f"http {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise OpenAICompatError(f"bad response: {e}") from e
        if not isinstance(text, str) or not text.strip():
            raise OpenAICompatError("empty content")
        return text.strip()
```

- [ ] **Step 4: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_pet_adapter_openai_compat.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pet_adapters/openai_compat.py backend/tests/test_pet_adapter_openai_compat.py
git commit -m "feat(pet): generic OpenAI-compatible chat adapter"
```

---

## Task 6: Pet gateway with provider registry

**Files:**
- Create: `backend/app/services/pet_gateway.py`
- Create: `backend/tests/test_pet_gateway.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.services import pet_gateway

pytestmark = pytest.mark.asyncio


@pytest.fixture
def secrets():
    """Resolves provider name -> api key (with model in extra)."""
    return {
        "zhipu":     {"key": "zk", "model": None},
        "qwen":      {"key": "qk", "model": None},
        "doubao":    {"key": "dk", "model": "ep-xxx"},
        "anthropic": {"key": "ak", "model": None},
    }


async def test_first_provider_succeeds_short_circuits(secrets):
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(return_value="hi")) as oc, \
         patch("app.services.pet_adapters.anthropic.chat", new=AsyncMock(return_value="x")) as an:
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen", "anthropic"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert (text, source) == ("hi", "zhipu")
        assert oc.call_count == 1
        assert an.call_count == 0


async def test_first_fails_second_succeeds(secrets):
    from app.services.pet_adapters.openai_compat import OpenAICompatError
    side = AsyncMock(side_effect=[OpenAICompatError("bad"), "ok"])
    with patch("app.services.pet_adapters.openai_compat.chat", new=side):
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert (text, source) == ("ok", "qwen")
        assert side.call_count == 2


async def test_all_fail_returns_fallback(secrets):
    from app.services.pet_adapters.openai_compat import OpenAICompatError
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(side_effect=OpenAICompatError("x"))), \
         patch("app.services.pet_adapters.anthropic.chat", new=AsyncMock(side_effect=Exception("x"))):
        text, source = await pet_gateway.summon(
            providers=["zhipu", "anthropic"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb1", "fb2"],
        )
        assert text in ("fb1", "fb2")
        assert source == "fallback"


async def test_empty_providers_returns_fallback(secrets):
    text, source = await pet_gateway.summon(
        providers=[],
        secrets=secrets,
        system="s", user="u",
        fallback_lines=["fb"],
    )
    assert text == "fb"
    assert source == "fallback"


async def test_missing_secret_skips_provider(secrets):
    secrets_partial = {"qwen": {"key": "qk", "model": None}}  # zhipu missing
    with patch("app.services.pet_adapters.openai_compat.chat", new=AsyncMock(return_value="ok")) as oc:
        text, source = await pet_gateway.summon(
            providers=["zhipu", "qwen"],
            secrets=secrets_partial,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert source == "qwen"
        assert oc.call_count == 1


async def test_doubao_uses_extra_model(secrets):
    captured = {}

    async def mock_chat(*, api_key, base_url, model, **kw):
        captured["model"] = model
        captured["base_url"] = base_url
        return "ok"

    with patch("app.services.pet_adapters.openai_compat.chat", new=mock_chat):
        await pet_gateway.summon(
            providers=["doubao"],
            secrets=secrets,
            system="s", user="u",
            fallback_lines=["fb"],
        )
        assert captured["model"] == "ep-xxx"
        assert "ark.cn-beijing.volces.com" in captured["base_url"]
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

- [ ] **Step 3: Implement gateway**

`backend/app/services/pet_gateway.py`:

```python
"""Pet gateway: tries providers in order, falls back to canned lines."""
from __future__ import annotations

import random
from typing import Any

import structlog

from app.services.pet_adapters import anthropic as anthropic_adapter
from app.services.pet_adapters import openai_compat

log = structlog.get_logger(__name__)


PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "zhipu": {
        "adapter": "openai_compat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "qwen": {
        "adapter": "openai_compat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "doubao": {
        "adapter": "openai_compat",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": None,  # endpoint id required from extra_json
    },
    "anthropic": {
        "adapter": "anthropic",
        "default_model": "claude-haiku-4-5-20251001",
    },
}


async def _call(
    *,
    name: str,
    api_key: str,
    model_override: str | None,
    system: str,
    user: str,
    timeout: float,
) -> str:
    cfg = PROVIDER_REGISTRY[name]
    model = model_override or cfg["default_model"]
    if model is None:
        raise RuntimeError(f"{name}: no model configured (set extra_json.model)")
    if cfg["adapter"] == "openai_compat":
        return await openai_compat.chat(
            api_key=api_key, base_url=cfg["base_url"], model=model,
            system=system, user=user, timeout=timeout,
        )
    if cfg["adapter"] == "anthropic":
        return await anthropic_adapter.chat(
            api_key=api_key, model=model,
            system=system, user=user, timeout=timeout,
        )
    raise RuntimeError(f"{name}: unknown adapter {cfg['adapter']!r}")


async def summon(
    *,
    providers: list[str],
    secrets: dict[str, dict[str, Any]],  # name -> {key, model}
    system: str,
    user: str,
    fallback_lines: list[str],
    timeout_per_call: float = 5.0,
) -> tuple[str, str]:
    """Try each provider in order. Return (text, source).

    `secrets[name]` shape: {"key": str, "model": str | None}.
    Providers without a secret entry are skipped.
    """
    for name in providers:
        if name not in PROVIDER_REGISTRY:
            log.warning("pet_gateway.unknown_provider", name=name)
            continue
        sec = secrets.get(name)
        if not sec or not sec.get("key"):
            log.info("pet_gateway.skip_no_secret", name=name)
            continue
        try:
            text = await _call(
                name=name,
                api_key=sec["key"],
                model_override=sec.get("model"),
                system=system,
                user=user,
                timeout=timeout_per_call,
            )
            return text, name
        except Exception as e:  # noqa: BLE001
            log.warning("pet_gateway.provider_failed", name=name, error=repr(e))
            continue
    return random.choice(fallback_lines) if fallback_lines else "...", "fallback"
```

- [ ] **Step 4: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_pet_gateway.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pet_gateway.py backend/tests/test_pet_gateway.py
git commit -m "feat(pet): pet_gateway with provider registry + fallback chain"
```

---

## Task 7: 3-layer rate limit helper

**Files:**
- Modify: `backend/app/services/rate_limit.py`
- Create: `backend/tests/test_pet_rate_limit.py`

- [ ] **Step 1: Write failing test**

```python
import pytest
from fakeredis.aioredis import FakeRedis

from app.services import rate_limit

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def redis():
    r = FakeRedis()
    yield r
    await r.flushall()
    await r.aclose()


async def test_check_pet_passes_under_limits(redis):
    res = await rate_limit.check_pet(
        redis, ip="1.2.3.4",
        per_ip_per_min=6, per_ip_per_day=30, global_per_day=500,
    )
    assert res is None  # no breach


async def test_check_pet_per_minute_breach(redis):
    for _ in range(6):
        await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=6, per_ip_per_day=30, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=6, per_ip_per_day=30, global_per_day=500)
    assert res == "per_ip_per_min"


async def test_check_pet_per_day_breach(redis):
    for _ in range(30):
        await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=999, per_ip_per_day=30, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.2.3.4", per_ip_per_min=999, per_ip_per_day=30, global_per_day=500)
    assert res == "per_ip_per_day"


async def test_check_pet_global_breach(redis):
    # Fill global with many IPs
    for i in range(500):
        await rate_limit.check_pet(redis, ip=f"10.0.0.{i % 255}",
                                   per_ip_per_min=999, per_ip_per_day=999, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="9.9.9.9",
                                     per_ip_per_min=999, per_ip_per_day=999, global_per_day=500)
    assert res == "global_per_day"


async def test_check_pet_returns_first_breach_only(redis):
    # Both per_min and per_day would breach — should report per_min (checked first)
    for _ in range(6):
        await rate_limit.check_pet(redis, ip="1.1.1.1", per_ip_per_min=6, per_ip_per_day=10, global_per_day=500)
    res = await rate_limit.check_pet(redis, ip="1.1.1.1", per_ip_per_min=6, per_ip_per_day=10, global_per_day=500)
    assert res == "per_ip_per_min"
```

- [ ] **Step 2: Run — expect FAIL** (no `check_pet`).

- [ ] **Step 3: Implement `check_pet`**

Append to `backend/app/services/rate_limit.py`:

```python
from datetime import UTC, datetime


async def check_pet(
    redis: Redis,
    *,
    ip: str,
    per_ip_per_min: int,
    per_ip_per_day: int,
    global_per_day: int,
) -> str | None:
    """Three-layer rate check for pet summon endpoint.

    Returns the name of the first breached layer, or None if all pass.
    All three counters are incremented as a side effect (so we don't double-count
    on the next request after a breach — we treat "still within window" as the
    state, not "consumed only after success").
    """
    today = datetime.now(UTC).strftime("%Y%m%d")
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
    # results: [count1, _, count2, _, count3, _]
    counts = [results[0], results[2], results[4]]
    for (label, _, limit, _), count in zip(keys, counts, strict=True):
        if int(count) > limit:
            return label
    return None
```

- [ ] **Step 4: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_pet_rate_limit.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rate_limit.py backend/tests/test_pet_rate_limit.py
git commit -m "feat(pet): 3-layer rate_limit.check_pet (per-IP/min, per-IP/day, global/day)"
```

---

## Task 8: Refactor /pet/summon endpoint

**Files:**
- Modify: `backend/app/routers/public/pet.py`
- Modify: `backend/tests/test_pet_summon.py`

- [ ] **Step 1: Write failing tests for the new payload**

Add to `backend/tests/test_pet_summon.py` (alongside existing tests):

```python
async def test_summon_greet_no_post(client):
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    j = r.json()
    assert "quip" in j and "source" in j


async def test_summon_comment_passes_post_title_to_prompt(client, fake_post_id, monkeypatch):
    captured = {}

    async def fake_summon(**kw):
        captured.update(kw)
        return ("hi", "zhipu")

    from app.services import pet_gateway
    monkeypatch.setattr(pet_gateway, "summon", fake_summon)

    r = await client.post("/api/pet/summon", json={"post_id": fake_post_id})
    assert r.status_code == 200
    # The user prompt should mention the article title
    assert "Title:" in captured["user"]


async def test_summon_explain_truncates_selection(client, fake_post_id, monkeypatch):
    captured = {}

    async def fake_summon(**kw):
        captured.update(kw)
        return ("explain ok", "zhipu")

    from app.services import pet_gateway
    monkeypatch.setattr(pet_gateway, "summon", fake_summon)

    long_sel = "x" * 2000
    r = await client.post(
        "/api/pet/summon",
        json={"post_id": fake_post_id, "selection": long_sel},
    )
    assert r.status_code == 200
    # Default max_context_chars is 500
    assert captured["user"].count("x") <= 500


async def test_summon_returns_tired_line_when_rate_limited(client, monkeypatch):
    async def fake_check_pet(*a, **kw):
        return "per_ip_per_min"

    from app.services import rate_limit
    monkeypatch.setattr(rate_limit, "check_pet", fake_check_pet)

    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    j = r.json()
    assert j["source"] == "rate_limited"
    assert j["quip"]  # non-empty
```

> `fake_post_id` fixture: add to `conftest.py` if missing — a fixture that inserts a Post row with id `"pet-test"` and yields it.

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Refactor the router**

Replace the body of `backend/app/routers/public/pet.py`:

```python
"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, SiteMeta
from app.redis import get_redis
from app.schemas.pet import PetConfig, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_gateway, rate_limit
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

router = APIRouter()


class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=80)
    selection: str | None = Field(default=None, max_length=4000)


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(s: AsyncSession = Depends(get_session)) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    return PublicPetConfig(
        species=cfg.species, hat=cfg.hat, tint=cfg.tint,
        enabled=cfg.enabled, visitor_can_change=cfg.visitor_can_change,
    )


def _build_prompt(
    cfg: PetConfig,
    *,
    post: Post | None,
    selection: str | None,
) -> tuple[str, str, str]:
    """Returns (system, user, mode)."""
    base_system = cfg.system_prompt
    if selection and post is not None and cfg.enable_article_context:
        explain_system = (
            "You are a tiny ASCII desktop pet that explains technical snippets "
            "in 1 short sentence. Mix English/Chinese naturally. No quotes."
        )
        sel = selection[: cfg.max_context_chars]
        return explain_system, f"From article '{post.title}', explain: {sel}", "explain"
    if post is not None and cfg.enable_article_context:
        summary = (post.summary or "")[:200]
        return base_system, f"Comment on this article. Title: {post.title}. Summary: {summary}", "comment"
    return base_system, "summon", "greet"


async def _resolve_secrets(s: AsyncSession, providers: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in providers:
        row = await integrations_svc.get(s, name=name)
        if row is None:
            continue
        from app.services import secret_box
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

    # Rate limit (3 layers)
    breach = await rate_limit.check_pet(
        redis, ip=ip_key,
        per_ip_per_min=cfg.per_ip_per_min,
        per_ip_per_day=cfg.per_ip_per_day,
        global_per_day=cfg.global_per_day,
    )
    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned",
            actor=ip_hash(client_ip_from(request))[:12],
            meta={"source": "rate_limited", "breach": breach},
        )
        await s.commit()
        return {"quip": quip, "source": "rate_limited"}

    # Resolve post
    post: Post | None = None
    if req.post_id:
        post = (await s.execute(select(Post).where(Post.id == req.post_id))).scalar_one_or_none()

    # Build prompt
    system, user, mode = _build_prompt(cfg, post=post, selection=req.selection)

    # Disabled / no providers / no secrets → fallback
    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        source = "fallback"
    else:
        secrets = await _resolve_secrets(s, cfg.providers)
        quip, source = await pet_gateway.summon(
            providers=cfg.providers,
            secrets=secrets,
            system=system,
            user=user,
            fallback_lines=cfg.fallback_lines,
        )

    await write_event(
        s, type="pet.summoned",
        actor=ip_hash(client_ip_from(request))[:12],
        meta={"source": source, "mode": mode},
    )
    await s.commit()
    return {"quip": quip, "source": source, "mode": mode}
```

- [ ] **Step 4: Add `fake_post_id` fixture if missing**

Append to `backend/tests/conftest.py`:

```python
@pytest.fixture
async def fake_post_id():
    from datetime import UTC, datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import engine
    from app.models import Post

    pid = "pet-test"
    async with AsyncSession(engine) as s:
        existing = await s.get(Post, pid)
        if existing is None:
            now = datetime.now(UTC)
            s.add(Post(
                id=pid, title="Pet Test", slug=pid, status="published",
                summary="A short summary.", body_md="# hi",
                created_at=now, updated_at=now, published_at=now,
            ))
            await s.commit()
    yield pid
```

> Adapt field set to actual `Post` schema if it differs (the file `backend/app/models/post.py` is the source of truth — read it and adjust required NOT NULL columns).

- [ ] **Step 5: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_pet_summon.py -v
```

- [ ] **Step 6: Remove the xfail markers added in Task 4 (they're now obsolete)**

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/public/pet.py backend/tests/test_pet_summon.py backend/tests/conftest.py
git commit -m "feat(pet): /pet/summon — payload routing, prompt builder, gateway call"
```

---

## Task 9: Admin endpoints for zhipu/qwen/doubao

**Files:**
- Modify: `backend/app/schemas/integration.py`
- Modify: `backend/app/routers/admin/integrations.py`
- Modify: `backend/tests/test_admin_integrations.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_admin_integrations.py`:

```python
async def test_get_zhipu_empty_returns_empty_envelope(client, admin_headers):
    r = await client.get("/api/admin/integrations/zhipu", headers=admin_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is False


async def test_put_zhipu_stores_secret_and_model(client, admin_headers, monkeypatch):
    # Mock the smoke test so we don't hit zhipu.com in unit tests
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/zhipu",
        headers=admin_headers,
        json={"token": "zhipu-key-xyz", "model": "glm-4-flash"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True
    assert j["model"] == "glm-4-flash"


async def test_put_zhipu_rejects_when_smoke_test_fails(client, admin_headers, monkeypatch):
    async def fake_chat(**kw):
        from app.services.pet_adapters.openai_compat import OpenAICompatError
        raise OpenAICompatError("auth failed")
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/zhipu",
        headers=admin_headers,
        json={"token": "bad", "model": "glm-4-flash"},
    )
    assert r.status_code == 422


async def test_put_qwen_stores_secret(client, admin_headers, monkeypatch):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/qwen",
        headers=admin_headers,
        json={"token": "qwen-key-xyz"},  # model omitted → server uses default
    )
    assert r.status_code == 200
    assert r.json()["configured"] is True
    assert r.json()["model"] == "qwen-turbo"


async def test_put_doubao_requires_model_in_payload(client, admin_headers):
    # No smoke test mock — should 422 on schema validation before reaching network
    r = await client.put(
        "/api/admin/integrations/doubao",
        headers=admin_headers,
        json={"token": "doubao-key"},  # missing required `model`
    )
    assert r.status_code == 422


async def test_put_doubao_with_model(client, admin_headers, monkeypatch):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)

    r = await client.put(
        "/api/admin/integrations/doubao",
        headers=admin_headers,
        json={"token": "doubao-key", "model": "ep-20260501-abc"},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "ep-20260501-abc"


async def test_get_qwen_after_put(client, admin_headers, monkeypatch):
    async def fake_chat(**kw):
        return "ok"
    from app.services.pet_adapters import openai_compat
    monkeypatch.setattr(openai_compat, "chat", fake_chat)
    await client.put("/api/admin/integrations/qwen", headers=admin_headers,
                     json={"token": "qk", "model": "qwen-plus"})
    r = await client.get("/api/admin/integrations/qwen", headers=admin_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["configured"] is True and j["model"] == "qwen-plus"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Add schemas**

Append to `backend/app/schemas/integration.py`:

```python
class _ProviderGet(BaseModel):
    configured: bool = False
    model: str | None = None
    last_synced_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


class ZhipuIntegrationGet(_ProviderGet): ...
class QwenIntegrationGet(_ProviderGet): ...
class DoubaoIntegrationGet(_ProviderGet): ...


class _ProviderPut(BaseModel):
    token: str = Field(min_length=4, max_length=512)
    model: str | None = Field(default=None, max_length=128)


class ZhipuIntegrationPut(_ProviderPut): ...
class QwenIntegrationPut(_ProviderPut): ...


class DoubaoIntegrationPut(BaseModel):
    token: str = Field(min_length=4, max_length=512)
    model: str = Field(min_length=4, max_length=128)  # endpoint id REQUIRED for doubao
```

- [ ] **Step 4: Add admin routes**

Append to `backend/app/routers/admin/integrations.py`:

```python
from app.services import pet_gateway
from app.services.pet_adapters import openai_compat


def _registry(name: str) -> dict:
    return pet_gateway.PROVIDER_REGISTRY[name]


async def _smoke(name: str, token: str, model: str) -> tuple[bool, str | None]:
    cfg = _registry(name)
    try:
        await openai_compat.chat(
            api_key=token,
            base_url=cfg["base_url"],
            model=model,
            system="ping", user="ping",
            max_tokens=4, timeout=5.0,
        )
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]


def _build_get(s: AsyncSession, name: str, schema_cls):
    async def _impl(_admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
        row = await svc.get(s, name=name)
        if row is None:
            return schema_cls()
        return schema_cls(
            configured=True,
            model=(row.extra_json or {}).get("model"),
            last_synced_at=row.last_synced_at,
            last_status=row.last_status,
            last_error=row.last_error,
        )
    return _impl


# Route handlers — three near-identical pairs:

@router.get("/integrations/zhipu", response_model=ZhipuIntegrationGet)
async def get_zhipu(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> ZhipuIntegrationGet:
    row = await svc.get(s, name="zhipu")
    if row is None:
        return ZhipuIntegrationGet()
    return ZhipuIntegrationGet(
        configured=True,
        model=(row.extra_json or {}).get("model"),
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.put(
    "/integrations/zhipu",
    response_model=ZhipuIntegrationGet,
    dependencies=[Depends(require_scope("write"))],
)
async def put_zhipu(
    req: ZhipuIntegrationPut,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> ZhipuIntegrationGet:
    model = req.model or pet_gateway.PROVIDER_REGISTRY["zhipu"]["default_model"]
    ok, err = await _smoke("zhipu", req.token, model)
    if not ok:
        raise HTTPException(422, f"zhipu smoke failed: {err}")
    await svc.upsert(s, name="zhipu", username=None, secret=req.token, extra={"model": model})
    await write_event(s, type="integration.zhipu.tested", actor=_admin.email, meta={"model": model})
    await s.commit()
    return ZhipuIntegrationGet(configured=True, model=model)


@router.get("/integrations/qwen", response_model=QwenIntegrationGet)
async def get_qwen(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> QwenIntegrationGet:
    row = await svc.get(s, name="qwen")
    if row is None:
        return QwenIntegrationGet()
    return QwenIntegrationGet(
        configured=True,
        model=(row.extra_json or {}).get("model"),
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.put(
    "/integrations/qwen",
    response_model=QwenIntegrationGet,
    dependencies=[Depends(require_scope("write"))],
)
async def put_qwen(
    req: QwenIntegrationPut,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> QwenIntegrationGet:
    model = req.model or pet_gateway.PROVIDER_REGISTRY["qwen"]["default_model"]
    ok, err = await _smoke("qwen", req.token, model)
    if not ok:
        raise HTTPException(422, f"qwen smoke failed: {err}")
    await svc.upsert(s, name="qwen", username=None, secret=req.token, extra={"model": model})
    await write_event(s, type="integration.qwen.tested", actor=_admin.email, meta={"model": model})
    await s.commit()
    return QwenIntegrationGet(configured=True, model=model)


@router.get("/integrations/doubao", response_model=DoubaoIntegrationGet)
async def get_doubao(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DoubaoIntegrationGet:
    row = await svc.get(s, name="doubao")
    if row is None:
        return DoubaoIntegrationGet()
    return DoubaoIntegrationGet(
        configured=True,
        model=(row.extra_json or {}).get("model"),
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.put(
    "/integrations/doubao",
    response_model=DoubaoIntegrationGet,
    dependencies=[Depends(require_scope("write"))],
)
async def put_doubao(
    req: DoubaoIntegrationPut,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DoubaoIntegrationGet:
    # doubao: model (endpoint id) is REQUIRED by DoubaoIntegrationPut schema — no default
    ok, err = await _smoke("doubao", req.token, req.model)
    if not ok:
        raise HTTPException(422, f"doubao smoke failed: {err}")
    await svc.upsert(s, name="doubao", username=None, secret=req.token, extra={"model": req.model})
    await write_event(s, type="integration.doubao.tested", actor=_admin.email, meta={"model": req.model})
    await s.commit()
    return DoubaoIntegrationGet(configured=True, model=req.model)
```

- [ ] **Step 5: Run tests — expect PASS**

```
cd backend && uv run pytest tests/test_admin_integrations.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/integration.py backend/app/routers/admin/integrations.py backend/tests/test_admin_integrations.py
git commit -m "feat(pet): admin endpoints for zhipu/qwen/doubao integrations"
```

---

## Task 10: Frontend — AsciiPet click handler payload routing

**Files:**
- Modify: `src/components/AsciiPet.jsx`
- Create: `src/components/pet/__tests__/payload.test.js`

- [ ] **Step 1: Write failing vitest test for the payload helper**

Create `src/components/pet/__tests__/payload.test.js`:

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { buildSummonPayload } from '../payload.js';

describe('buildSummonPayload', () => {
  beforeEach(() => {
    // Mock window.location.pathname & window.getSelection
    Object.defineProperty(window, 'location', {
      value: { pathname: '/' }, writable: true,
    });
    window.getSelection = () => ({ toString: () => '' });
  });

  it('returns greet on home', () => {
    expect(buildSummonPayload(500)).toEqual({});
  });

  it('returns comment on article without selection', () => {
    window.location.pathname = '/p/abc123';
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc123' });
  });

  it('returns explain on article with selection >=5 chars', () => {
    window.location.pathname = '/p/abc123';
    window.getSelection = () => ({ toString: () => 'hello world' });
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc123', selection: 'hello world' });
  });

  it('truncates selection to maxChars', () => {
    window.location.pathname = '/p/abc';
    window.getSelection = () => ({ toString: () => 'x'.repeat(2000) });
    const out = buildSummonPayload(500);
    expect(out.selection.length).toBe(500);
  });

  it('ignores tiny selections (<5 chars)', () => {
    window.location.pathname = '/p/abc';
    window.getSelection = () => ({ toString: () => 'ab' });
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc' });
  });
});
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

```
npx vitest run src/components/pet/__tests__/payload.test.js
```

- [ ] **Step 3: Implement the helper**

Create `src/components/pet/payload.js`:

```js
const POST_RE = /^\/p\/([^/]+)/;

/**
 * Inspect URL + current selection and return the payload to send to /api/pet/summon.
 * - On home: {}
 * - On article without selection: {post_id}
 * - On article with selection >= 5 chars: {post_id, selection: <truncated>}
 */
export function buildSummonPayload(maxChars = 500) {
  const m = window.location.pathname.match(POST_RE);
  if (!m) return {};
  const post_id = decodeURIComponent(m[1]);
  const sel = (window.getSelection?.()?.toString() || '').trim();
  if (sel.length >= 5) {
    return { post_id, selection: sel.slice(0, maxChars) };
  }
  return { post_id };
}
```

- [ ] **Step 4: Wire into AsciiPet.jsx**

In `src/components/AsciiPet.jsx`, replace `summonSpeech` body so it calls the API:

```js
import { buildSummonPayload } from './pet/payload.js';

// inside summonSpeech:
const summonSpeech = async () => {
  clearTimeout(speechTimer.current);
  setSpeech({ text: '…', thinking: true });
  setState('thinking');
  tempStateUntil.current = Date.now() + 8000;
  let text = null;
  try {
    const payload = buildSummonPayload(500);
    const r = await fetch('/api/pet/summon', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (r.ok) {
      const j = await r.json();
      text = (j.quip || '').trim().slice(0, 80);
    }
  } catch (_) { /* fall through to canned reply */ }
  if (!text) text = QUIPS[Math.floor(Math.random() * QUIPS.length)];
  setSpeech({ text });
  setState('happy');
  tempStateUntil.current = Date.now() + 1400;
  clearTimeout(speechTimer.current);
  speechTimer.current = setTimeout(() => setSpeech(null), 8000);
};
```

> Remove the old `window.claude.complete` block — the gateway is now the server.

- [ ] **Step 5: Run vitest — expect PASS**

- [ ] **Step 6: Manual smoke**

```
npm run dev
```

Visit `/`, click pet → bubble shows quip. Visit `/p/<some-id>`, select 10 characters, click pet → quip is selection-aware (verify via Network tab payload). Verify rate limit by clicking 7 times — 7th should return tired_line.

- [ ] **Step 7: Commit**

```bash
git add src/components/pet/payload.js src/components/pet/__tests__/payload.test.js src/components/AsciiPet.jsx
git commit -m "feat(pet): client posts {post_id, selection} to /api/pet/summon"
```

---

## Task 11: Frontend — selectionchange hint in Reader

**Files:**
- Modify: `src/components/Reader.jsx`
- Modify: `src/components/AsciiPet.jsx`
- Modify: `src/App.jsx`

- [ ] **Step 1: Lift `petHint` state into App**

In `src/App.jsx` add:

```jsx
const [petHint, setPetHint] = useState(null);
```

Pass `setPetHint` to `Reader`: `<Reader post={reading} onBack={closePost} onOpenPost={openPost} onSelection={setPetHint} />`. Pass `hint={petHint}` to `AsciiPet`.

- [ ] **Step 2: Reader listens to selectionchange**

In `src/components/Reader.jsx` add inside the component:

```jsx
useEffect(() => {
  if (!onSelection) return undefined;
  let timer = null;
  const handler = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const sel = (window.getSelection?.()?.toString() || '').trim();
      if (sel.length >= 5) {
        onSelection({ text: 'click pet to explain ↑', kind: 'explain' });
        // auto-clear after 2s
        setTimeout(() => onSelection(null), 2000);
      }
    }, 200);
  };
  document.addEventListener('selectionchange', handler);
  return () => {
    document.removeEventListener('selectionchange', handler);
    clearTimeout(timer);
  };
}, [onSelection]);
```

- [ ] **Step 3: AsciiPet renders hint**

In `src/components/AsciiPet.jsx`, accept `hint` prop and render it as the bubble when no `speech` is showing:

```jsx
export default function AsciiPet({ hint = null }) {
  // ... existing code ...
  const bubbleText = speech?.text || hint?.text;
  const bubbleThinking = speech?.thinking;
  // Replace the {speech && ...} block with:
  {bubbleText && !mini && (
    <div className="clawd-bubble" style={{ borderColor: color, color }}>
      <span>{bubbleThinking ? <Dots /> : bubbleText}</span>
      <span className="clawd-bubble-arrow" style={{ '--bc': color }} />
    </div>
  )}
}
```

- [ ] **Step 4: Manual smoke**

```
npm run dev
```

Open `/p/<some-id>`. Select 10 characters → bubble appears with "click pet to explain ↑", fades after 2s. Click pet while selection is alive → bubble switches to LLM quip about the selection.

- [ ] **Step 5: Commit**

```bash
git add src/components/Reader.jsx src/components/AsciiPet.jsx src/App.jsx
git commit -m "feat(pet): selection hint bubble — 'click pet to explain' on Reader"
```

---

## Task 12: Frontend — species.js with 18 buddy-editor templates

**Files:**
- Create: `src/components/pet/species.js`
- Create: `src/components/pet/__tests__/species.test.js`

- [ ] **Step 1: Write failing test**

Create `src/components/pet/__tests__/species.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { SPECIES, RARITY_ORDER, byRarity } from '../species.js';

describe('SPECIES', () => {
  it('has at least 18 entries (18 from buddy-editor + 4 legendary in Task 14)', () => {
    expect(Object.keys(SPECIES).length).toBeGreaterThanOrEqual(18);
  });

  it('each entry has color, rarity, frames (3 frames, 5 lines each, all 12 chars wide)', () => {
    for (const [key, sp] of Object.entries(SPECIES)) {
      expect(sp.color, key).toMatch(/^#[0-9a-f]{3,8}$/i);
      expect(RARITY_ORDER, key).toContain(sp.rarity);
      expect(sp.frames, key).toHaveLength(3);
      for (const frame of sp.frames) {
        expect(frame, key).toHaveLength(5);
        for (const line of frame) {
          // Width including {E} placeholder normalized: substitute {E} with X for length check
          const w = line.replace(/\{E\}/g, 'X').length;
          expect(w, `${key}: line "${line}"`).toBe(12);
        }
      }
    }
  });

  it('byRarity groups species by rarity preserving RARITY_ORDER', () => {
    const groups = byRarity();
    const orderedKeys = Object.keys(groups);
    expect(orderedKeys).toEqual(RARITY_ORDER.filter((r) => groups[r].length > 0));
  });
});
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

- [ ] **Step 3: Create species.js**

Copy the 18 templates from `/tmp/buddy-skin-editor/index.html` (`SPECIES_TEMPLATES`, lines 723–743). The format is `[[5 lines], [5 lines], [5 lines]]`. Wrap each into the schema below.

`src/components/pet/species.js`:

```js
// Imported from dead1786/buddy-skin-editor (MIT). 18 templates verbatim.
// Each species: 3 frames × 5 lines × 12 chars; `{E}` marks eye positions.

export const RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];

export const RARITY_COLOR = {
  common:    '#9aa6b3',
  uncommon:  '#7dbf8e',
  rare:      '#5c9ddc',
  epic:      '#b89cf0',
  legendary: '#f5b44c',
};

export const SPECIES = {
  duck: {
    rarity: 'common', color: '#f5d44c',
    frames: [
      ["            ","    __      ","  <({E} )___  ","   (  ._>   ","    `--´    "],
      ["            ","    __      ","  <({E} )___  ","   (  ._>   ","    `--´~   "],
      ["            ","    __      ","  <({E} )___  ","   (  .__>  ","    `--´    "],
    ],
  },
  goose: {
    rarity: 'common', color: '#e8e8e8',
    frames: [
      ["            ","     ({E}>    ","     ||     ","   _(__)_   ","    ^^^^    "],
      ["            ","    ({E}>     ","     ||     ","   _(__)_   ","    ^^^^    "],
      ["            ","     ({E}>>   ","     ||     ","   _(__)_   ","    ^^^^    "],
    ],
  },
  blob: {
    rarity: 'common', color: '#7dd3a4',
    frames: [
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (      )  ","   `----´   "],
      ["            ","  .------.  "," (  {E}  {E}  ) "," (        ) ","  `------´  "],
      ["            ","    .--.    ","   ({E}  {E})   ","   (    )   ","    `--´    "],
    ],
  },
  cat: {
    rarity: 'common', color: '#e0a96d',
    frames: [
      ["            ","   /\\__/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")   '],
      ["            ","   /\\__/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")~  '],
      ["            ","   /\\--/\\   ","  ( {E}  {E} )  ","  (  ω   )  ",'  (")__(")   '],
    ],
  },
  rabbit: {
    rarity: 'common', color: '#f0d8e0',
    frames: [
      ["            ","   (\\__/)   ","  ( {E}  {E} )  "," =(  ..  )= ",'  (")__(")  '],
      ["            ","   (|__/)   ","  ( {E}  {E} )  "," =(  ..  )= ",'  (")__(")  '],
      ["            ","   (\\__/)   ","  ( {E}  {E} )  "," =( .  . )= ",'  (")__(")  '],
    ],
  },
  penguin: {
    rarity: 'uncommon', color: '#5c7ec4',
    frames: [
      ["            "," .-o-OO-o-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
      ["            "," .-O-oo-O-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
      ["   . o  .   "," .-o-OO-o-. ","(__________)","   |{E}  {E}|   ","   |____|   "],
    ],
  },
  owl: {
    rarity: 'uncommon', color: '#a89060',
    frames: [
      ["            ","   /\\  /\\   ","  (({E})({E}))  ","  (  ><  )  ","   `----´   "],
      ["            ","   /\\  /\\   ","  (({E})({E}))  ","  (  ><  )  ","   .----.   "],
      ["            ","   /\\  /\\   ","  (({E})(-))  ","  (  ><  )  ","   `----´   "],
    ],
  },
  turtle: {
    rarity: 'uncommon', color: '#7da888',
    frames: [
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[______]\\ ","  ``    ``  "],
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[______]\\ ","   ``  ``   "],
      ["            ","   _,--._   ","  ( {E}  {E} )  "," /[======]\\ ","  ``    ``  "],
    ],
  },
  capybara: {
    rarity: 'uncommon', color: '#d4a574',
    frames: [
      ["            ","  n______n  "," ( {E}    {E} ) "," (   oo   ) ","  `------´  "],
      ["            ","  n______n  "," ( {E}    {E} ) "," (   Oo   ) ","  `------´  "],
      ["    ~  ~    ","  u______n  "," ( {E}    {E} ) "," (   oo   ) ","  `------´  "],
    ],
  },
  mushroom: {
    rarity: 'rare', color: '#d05a5a',
    frames: [
      ["            ","  .---.     ","  ({E}>{E})     "," /(   )\\    ","  `---´     "],
      ["            ","  .---.     ","  ({E}>{E})     "," |(   )|    ","  `---´     "],
      ["  .---.     ","  ({E}>{E})     "," /(   )\\    ","  `---´     ","   ~ ~      "],
    ],
  },
  ghost: {
    rarity: 'rare', color: '#c8c8e0',
    frames: [
      ["            ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  ~`~``~`~  "],
      ["            ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  `~`~~`~`  "],
      ["    ~  ~    ","   .----.   ","  / {E}  {E} \\  ","  |      |  ","  ~~`~~`~~  "],
    ],
  },
  snail: {
    rarity: 'rare', color: '#b89060',
    frames: [
      ["            "," {E}    .--.  ","  \\  ( @ )  ","   \\_`--´   ","  ~~~~~~~   "],
      ["            ","  {E}   .--.  ","  |  ( @ )  ","   \\_`--´   ","  ~~~~~~~   "],
      ["            "," {E}    .--.  ","  \\  ( @  ) ","   \\_`--´   ","   ~~~~~~   "],
    ],
  },
  cactus: {
    rarity: 'rare', color: '#7dbf8e',
    frames: [
      ["            "," n  ____  n "," | |{E}  {E}| | "," |_|    |_| ","   |    |   "],
      ["            ","    ____    "," n |{E}  {E}| n "," |_|    |_| ","   |    |   "],
      [" n        n "," |  ____  | "," | |{E}  {E}| | "," |_|    |_| ","   |    |   "],
    ],
  },
  chonk: {
    rarity: 'rare', color: '#c4a484',
    frames: [
      ["            ","  /\\    /\\  "," ( {E}    {E} ) "," (   ..   ) ","  `------´  "],
      ["            ","  /\\    /|  "," ( {E}    {E} ) "," (   ..   ) ","  `------´  "],
      ["            ","  /\\    /\\  "," ( {E}    {E} ) "," (   ..   ) ","  `------´~ "],
    ],
  },
  octopus: {
    rarity: 'epic', color: '#b89cf0',
    frames: [
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  /\\/\\/\\/\\  "],
      ["            ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  \\/\\/\\/\\/  "],
      ["     o      ","   .----.   ","  ( {E}  {E} )  ","  (______)  ","  /\\/\\/\\/\\  "],
    ],
  },
  jellyfish: {
    rarity: 'epic', color: '#a4d4e8',
    frames: [
      ["            ","  ╭━━━━━━╮ "," ╭  {E}  {E}  ╮","  ╰┬┬┬┬┬┬╯ ","   ┆┆┆┆┆┆  "],
      ["            ","  ╭━━━━━━╮ "," ╭  {E}  {E}  ╮","  ╰┬┬┬┬┬┬╯ ","   ∫∫∫∫∫∫  "],
      ["            ","  ╭━━━━━━╮ "," ╭  {E}  {E}  ╮","  ╰┬┬┬┬┬┬╯ ","   ┆┆┆┆┆┆  "],
    ],
  },
  axolotl: {
    rarity: 'epic', color: '#f0a4d4',
    frames: [
      ["            ","}~(______)~{","}~({E} .. {E})~{","  ( .--. )  ","  (_/  \\_)  "],
      ["            ","~}(______){~","~}({E} .. {E}){~","  ( .--. )  ","  (_/  \\_)  "],
      ["            ","}~(______)~{","}~({E} .. {E})~{","  (  --  )  ","  ~_/  \\_~  "],
    ],
  },
  robot: {
    rarity: 'epic', color: '#7cc7f0',
    frames: [
      ["            ","   .[||].   ","  [ {E}  {E} ]  ","  [ ==== ]  ","  `------´  "],
      ["            ","   .[||].   ","  [ {E}  {E} ]  ","  [ -==- ]  ","  `------´  "],
      ["     *      ","   .[||].   ","  [ {E}  {E} ]  ","  [ ==== ]  ","  `------´  "],
    ],
  },
  dragon: {
    rarity: 'legendary', color: '#ff7a5c',
    frames: [
      ["            ","  /^\\  /^\\  "," <  {E}  {E}  > "," (   ~~   ) ","  `-vvvv-´  "],
      ["            ","  /^\\  /^\\  "," <  {E}  {E}  > "," (        ) ","  `-vvvv-´  "],
      ["   ~    ~   ","  /^\\  /^\\  "," <  {E}  {E}  > "," (   ~~   ) ","  `-vvvv-´  "],
    ],
  },
};

export function byRarity() {
  const out = {};
  for (const r of RARITY_ORDER) out[r] = [];
  for (const [key, sp] of Object.entries(SPECIES)) {
    out[sp.rarity].push({ key, ...sp });
  }
  // drop empty buckets so the panel doesn't render blank rows
  for (const r of RARITY_ORDER) {
    if (out[r].length === 0) delete out[r];
  }
  return out;
}

// Mapping from pet state to {E} substitute character.
export const STATE_EYE = {
  idle:         '·',
  thinking:     '°',
  typing:       '·',
  building:     'o',
  juggling:     '^',
  conducting:   '^',
  error:        '×',
  happy:        '✦',
  notification: '>',
  sweeping:     '-',
  carrying:     'o',
  sleeping:     '-',
  yawning:      '>',
  startled:     '◉',
};
```

> Sanity-check: open `/tmp/buddy-skin-editor/index.html` line 723 and confirm exact-match strings. The `width === 12` test will catch any miscopy.

- [ ] **Step 4: Run tests — expect PASS**

```
npx vitest run src/components/pet/__tests__/species.test.js
```

- [ ] **Step 5: Commit**

```bash
git add src/components/pet/species.js src/components/pet/__tests__/species.test.js
git commit -m "feat(pet): import 18 species from buddy-skin-editor"
```

---

## Task 13: Refactor AsciiPet to consume species.js

**Files:**
- Modify: `src/components/AsciiPet.jsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Replace `BODY` and `BODY_ORDER` with imports**

At the top of `src/components/AsciiPet.jsx`:

```jsx
import { SPECIES, RARITY_ORDER, RARITY_COLOR, byRarity, STATE_EYE } from './pet/species.js';
```

Delete the local `BODY = { capybara: ..., cat: ..., dragon: ..., octopus: ..., robot: ... }` and `BODY_ORDER` constants.

- [ ] **Step 2: Replace `renderSprite` for single-eye placeholder**

```jsx
function renderSprite(frame, eye) {
  return frame.map((line) => line.replaceAll('{E}', eye)).join('\n');
}
```

(Drop the old `{L}{R}{M}` substitution.)

- [ ] **Step 3: localStorage migration map for old species names**

```jsx
const LEGACY_BODY_MAP = {
  // old key → new key (the new SPECIES has same names for cat/capybara/dragon/octopus/robot)
  capybara: 'capybara',
  cat: 'cat',
  dragon: 'dragon',
  octopus: 'octopus',
  robot: 'robot',
};

const [bodyKey, setBodyKey] = useState(() => {
  const saved = localStorage.getItem('pet.body');
  if (!saved) return 'cat';
  if (SPECIES[saved]) return saved;
  if (LEGACY_BODY_MAP[saved] && SPECIES[LEGACY_BODY_MAP[saved]]) {
    return LEGACY_BODY_MAP[saved];
  }
  return 'cat';
});
const body = SPECIES[bodyKey] || SPECIES.cat;
```

- [ ] **Step 4: Replace eye/mouth rendering**

In the existing render block, replace:

```jsx
const cfg = STATES[state] || STATES.idle;
let L = cfg.eyes[0];
let R = cfg.eyes[1];
// gaze override
const M = cfg.mouth;
const sprite = renderSprite(body.base[frame], L, R, M);
```

with:

```jsx
const cfg = STATES[state] || STATES.idle;
let eye = STATE_EYE[state] || '·';
if (state === 'idle') {
  if (gaze.x < -0.3) eye = '◂';
  else if (gaze.x > 0.3) eye = '▸';
  else if (gaze.y < -0.3) eye = '°';
  else if (gaze.y > 0.3) eye = '.';
}
const sprite = renderSprite(body.frames[frame % body.frames.length], eye);
```

(`cfg.mouth` is unused — remove. `body.frames` replaces `body.base`.)

- [ ] **Step 5: Replace species panel grid with rarity grouping**

Inside the panel JSX, replace the existing flat grid with:

```jsx
{Object.entries(byRarity()).map(([rarity, list]) => (
  <div key={rarity} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <div style={{
      fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
      color: RARITY_COLOR[rarity],
    }}>{rarity}</div>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {list.map(({ key }) => (
        <button
          key={key}
          className={`pet-panel-chip ${key === bodyKey ? 'on' : ''} rarity-${rarity}`}
          onClick={() => { setBodyKey(key); localStorage.setItem('pet.body', key); }}
          style={{
            '--c': SPECIES[key].color,
            fontSize: 10, padding: '4px 7px',
            border: `1px solid ${rarity === 'legendary' ? '#f5b44c' : 'var(--line)'}`,
            borderRadius: 3,
            background: key === bodyKey ? `color-mix(in oklab, ${SPECIES[key].color} 14%, var(--bg-3))` : 'var(--bg-3)',
            color: key === bodyKey ? SPECIES[key].color : 'var(--fg-3)',
            cursor: 'pointer', whiteSpace: 'nowrap',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >{key}</button>
      ))}
    </div>
  </div>
))}
```

- [ ] **Step 6: Manual smoke**

```
npm run dev
```

Open page, expand pet panel, verify all 18 species are listed grouped by rarity (legendary should show "dragon" with gold border). Click each — pet redraws. Sleep / hover / click states still work.

- [ ] **Step 7: Commit**

```bash
git add src/components/AsciiPet.jsx src/styles.css
git commit -m "refactor(pet): consume species.js + state→eye-char + rarity-grouped panel"
```

---

## Task 14: Hand-author 4 legendary buddies

**Files:**
- Modify: `src/components/pet/species.js`
- Modify: `src/components/pet/__tests__/species.test.js`

- [ ] **Step 1: Update test to expect 22 species**

Change in `species.test.js`:

```js
expect(Object.keys(SPECIES).length).toBe(22);
```

Run — expect FAIL.

- [ ] **Step 2: Author 4 legendary species**

Each must be 12 chars wide × 5 lines × 3 frames, with `{E}` for eye position. Append to `SPECIES` in `src/components/pet/species.js`:

```js
  // ===== Hand-authored legendary buddies =====

  phoenix: {
    rarity: 'legendary', color: '#ff9544',
    frames: [
      ["    ^^^^    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","   ^^^^^    "],
      ["   ^^^^^    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","  ^vvvvv^   "],
      ["    *  *    ","   /^v^\\    ","  ( {E}  {E} )  ","   \\___/    ","   ^^^^^    "],
    ],
  },

  fox: {
    rarity: 'legendary', color: '#f08c5c',
    frames: [
      ["            ","   /\\__/\\   ","  ( {E}><{E} )  ","   \\_vv_/   ","   /    \\~  "],
      ["            ","   /\\__/\\   ","  ( {E}>>{E} )  ","   \\_vv_/   ","  ~/    \\   "],
      ["            ","   /\\__/\\   ","  ( {E}><{E} )  ","   \\_..__/  ","   /    \\~  "],
    ],
  },

  shiba: {
    rarity: 'legendary', color: '#e8a474',
    frames: [
      ["            ","  /\\____/\\  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
      ["            ","  /\\____/|  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
      ["    *       ","  /\\____/\\  "," (  {E}  {E}  ) "," (   ww   ) ","  `--uu--´  "],
    ],
  },

  mochi: {
    rarity: 'legendary', color: '#fff0e8',
    frames: [
      ["            ","   .----.   ","  ( {E} ω {E} )  ","   `----´   ","   ~~~~~~   "],
      ["            ","  .------.  "," ( {E}  ω  {E} )"," (        )","   ~~~~~~   "],
      ["    ~~      ","   .----.   ","  ( {E} ω {E} )  ","   `----´   ","   ~~~~~~   "],
    ],
  },
```

> Width verification: count each line — must be exactly 12 chars after replacing `{E}` with one char. The vitest test will catch errors. If a line is off by 1, pad with a single space at the end.

- [ ] **Step 3: Run tests — expect PASS**

```
npx vitest run src/components/pet/__tests__/species.test.js
```

If width-check fails on any line, fix the spacing inline and re-run.

- [ ] **Step 4: Manual smoke**

```
npm run dev
```

Open pet panel — legendary group now has 5 species (dragon + phoenix + fox + shiba + mochi). Click each, verify it renders centered, no visual breakage on different states.

- [ ] **Step 5: Commit**

```bash
git add src/components/pet/species.js src/components/pet/__tests__/species.test.js
git commit -m "feat(pet): 4 legendary buddies — phoenix/fox/shiba/mochi"
```

---

## Task 15: End-to-end smoke + cleanup

**Files:** none (verification + final commit)

- [ ] **Step 1: Run full backend test suite**

```
cd backend && uv run pytest -q
```
Expected: all green.

- [ ] **Step 2: Run full frontend test suite**

```
npx vitest run
```
Expected: all green.

- [ ] **Step 3: Manual end-to-end smoke**

Start backend + redis + frontend:
```
docker compose up -d postgres redis
cd backend && uv run uvicorn app.main:app --reload &
npm run dev
```

In browser:
- (a) Visit `/` (home) — pet sits there. Click pet → bubble shows fallback line ("compiling thoughts...") because no provider key is configured. Open DevTools → Network → confirm POST to `/api/pet/summon` returns `source: "fallback"`.
- (b) Visit `/admin/integrations` — configure 智谱 with a real key. PUT succeeds → smoke test green.
- (c) Back to `/`, click pet → quip changes (LLM source). Network tab: `source: "zhipu"`.
- (d) Visit `/p/<some-id>` — pet still visible. Click pet without selection → quip references the article title.
- (e) Select 10 chars in article body → bubble shows "click pet to explain ↑". Click pet → quip explains the selection.
- (f) Click pet 7 times in a minute → 7th returns a tired_line, `source: "rate_limited"`.
- (g) Open pet panel → 22 species in 5 rarity rows; legendary row shows `dragon`/`phoenix`/`fox`/`shiba`/`mochi` with gold borders. Click each, verify rendering.
- (h) Refresh page — pet remembers chosen species (`localStorage.pet.body`). Inject old key in console: `localStorage.setItem('pet.body', 'capybara')` then refresh — pet shows new buddy-editor capybara, not crash.

- [ ] **Step 4: Lint + typecheck**

```
cd backend && uv run ruff check .
npx eslint src/
```

Fix any new violations (no new lints expected since we matched existing patterns).

- [ ] **Step 5: Final commit (only if anything was tweaked above)**

```bash
git add -A
git commit -m "chore(pet): close-out smoke fixes"
```

(Skip if no changes.)

---

## Spec Coverage Self-Check

| Spec section                                  | Implemented in   |
|-----------------------------------------------|------------------|
| Gateway architecture (PROVIDER_REGISTRY)      | Task 6           |
| Adapters: zhipu/qwen/doubao via OpenAI-compat | Tasks 5, 6       |
| Adapter: Anthropic refactor                   | Task 4           |
| Alembic migration (CHECK relax)               | Task 1           |
| Integration model + service                   | Task 2           |
| PetConfig schema (providers, rate, tired)     | Task 3           |
| 3-mode prompt builder                         | Task 8           |
| 3-layer rate limit                            | Task 7           |
| /pet/summon refactor                          | Task 8           |
| Admin endpoints (3 providers)                 | Task 9           |
| Frontend payload routing                      | Task 10          |
| Selection hint bubble                         | Task 11          |
| species.js with 18 templates                  | Task 12          |
| AsciiPet refactor (single eye)                | Task 13          |
| 4 legendary buddies                           | Task 14          |
| Settings panel rarity grouping                | Task 13          |
| End-to-end smoke                              | Task 15          |
| Tests (gateway, rate_limit, pet_summon, ...)  | Tasks 1–9, 10, 12 |
