# Pet 升级 — 多厂商 LLM Gateway + 上下文感知 + 皮肤迁移

**Date**: 2026-05-01
**Status**: Approved (brainstorm phase)
**Scope**: 一次性落地，分阶段实施

## 背景与目标

当前 pet（`AsciiPet.jsx` + `routers/public/pet.py` + `pet_llm.py`）只支持 Anthropic 单一厂商，且只在被点击时随机说一句俏皮话，与文章上下文无关。

升级目标：

1. 把 LLM 后端抽象成 gateway，先接入 3 家国内厂商（智谱 GLM、通义千问、豆包）+ 保留 Anthropic，支持顺序降级。
2. 文章页点 pet 能基于文章/选中段落给出相关回复。
3. 限流分 3 层（per-IP/min、per-IP/day、global/day）防 token 被刷。
4. 兜底机制：LLM 失败、限流命中、上下文缺失时回退到固定话术或 "pets 累了" 类语料。
5. 皮肤系统：把 `dead1786/buddy-skin-editor` 的 18 个 species 全量迁过来，再手写 4 个 legendary 稀有款，完全替换现有的 5 个 ASCII 角色（共 22 个）。

## 非目标

- 不接入 MiniMax 与小米（暂缓；gateway 抽象后随时可加）。
- 不做用户登录后的 per-account 配额（当前是 IP 维度即可）。
- 不做 streaming（一次性返回，max_tokens 80 已经够短）。
- 不做选中文本的浮动工具条（仅做 "click pet" 提示气泡）。

## 架构

```
┌────────────────────────────────────────────────────────────┐
│ Frontend                                                    │
│  AsciiPet.jsx                                               │
│  ├─ click handler → builds payload {mode, post_id, sel}    │
│  ├─ Reader.jsx hooks selectionchange → shows hint bubble   │
│  └─ species.js (18 + 4 legendary = 22 templates)           │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /api/pet/summon
                       ▼
┌────────────────────────────────────────────────────────────┐
│ FastAPI                                                     │
│  routers/public/pet.py                                      │
│  ├─ rate_limit.check (3 layers)                            │
│  ├─ build_prompt(mode, post)                               │
│  └─ pet_gateway.summon(...)                                │
│         │                                                   │
│         ▼  (try in order, fallback on failure)             │
│  services/pet_gateway.py                                    │
│  ├─ adapters/zhipu.py                                       │
│  ├─ adapters/qwen.py                                        │
│  ├─ adapters/doubao.py                                      │
│  └─ adapters/anthropic.py (existing logic moved here)      │
└────────────────────────────────────────────────────────────┘
```

### Gateway 接口（Portkey 风格）

每个 adapter 实现：

```python
class ProviderAdapter(Protocol):
    name: str  # "zhipu" / "qwen" / "doubao" / "anthropic"
    async def chat(
        self,
        *,
        api_key: str,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 80,
        temperature: float = 0.9,
        timeout: float = 5.0,
    ) -> str: ...
```

Gateway 顶层：

```python
async def summon(
    s: AsyncSession,
    *,
    providers: list[str],   # ordered, e.g. ["zhipu", "qwen", "doubao"]
    system: str,
    user: str,
    fallback_lines: list[str],
) -> tuple[str, str]:
    """Returns (text, source). source ∈ provider names | 'fallback'."""
```

总预算 10s（默认走完前 2 家就停；第 3 家不再尝试）。每家超时 5s。

## 数据模型变更

### Alembic migration `0008_pet_multi_provider.py`

1. 放宽 `integrations.name` CHECK 约束：
   ```sql
   ALTER TABLE integrations DROP CONSTRAINT ck_integrations_name;
   ALTER TABLE integrations ADD CONSTRAINT ck_integrations_name
     CHECK (name IN ('github','anthropic','zhipu','qwen','doubao'));
   ```
2. 不动 `integrations` 表结构 — 现有 `secret_encrypted` / `extra_json` 已能容纳新厂商。

### `Integration` 模型同步更新

```python
__table_args__ = (
    CheckConstraint(
        "name IN ('github','anthropic','zhipu','qwen','doubao')",
        name="ck_integrations_name",
    ),
)
```

`integrations.upsert()` 的 `Literal` 类型也同步扩。

### `PetConfig`（pydantic）新增字段

```python
class PetConfig(_Strict):
    # ... existing fields ...
    providers: list[str] = Field(
        default_factory=lambda: ["zhipu"],
        max_length=4,
    )  # ordered fallback chain
    per_ip_per_min: int = Field(default=6, ge=1, le=60)        # renamed from rate_limit_per_min
    per_ip_per_day: int = Field(default=30, ge=1, le=500)
    global_per_day: int = Field(default=500, ge=10, le=10000)
    max_context_chars: int = Field(default=500, ge=100, le=2000)
    enable_article_context: bool = True
    tired_lines: list[str] = Field(
        min_length=1,
        default_factory=lambda: ["pets 累了…", "let me nap a bit, k?"],
    )
```

> 旧的 `rate_limit_per_min` 字段保留为 alias 一周（兼容旧数据），之后删。

## 客户端调用流程

### 三种 mode

| mode      | 触发条件                                          | payload                                   |
|-----------|---------------------------------------------------|-------------------------------------------|
| `greet`   | 路径不是 `/p/:id`，或 `enable_article_context=false`  | `{}`                                      |
| `comment` | 在 `/p/:id` 但 `window.getSelection()` 为空        | `{post_id}`                               |
| `explain` | 在 `/p/:id` 且选中文字 ≥ 5 字符                    | `{post_id, selection: <≤500 chars>}`     |

前端在调用前截断 selection：`selection.slice(0, max_context_chars)`，防止误传超长选区。

### Prompt 拼接（后端）

```python
def build_prompt(mode: str, post: Post | None, selection: str | None) -> tuple[str, str]:
    """Returns (system, user)."""
    base_system = (
        "You are a tiny ASCII desktop pet on a developer's blog. "
        "Reply ONE short playful line (max 20 Chinese chars or 12 English words). "
        "Mix English/Chinese naturally. No quotes, no emoji."
    )
    if mode == "greet":
        return base_system, "summon"
    if mode == "comment":
        return base_system, (
            f"Comment on this article. Title: {post.title}. "
            f"Summary: {post.summary[:200] if post.summary else ''}"
        )
    if mode == "explain":
        explain_system = (
            "You are a tiny ASCII desktop pet that explains technical snippets "
            "in 1 short sentence. Mix English/Chinese naturally. No quotes."
        )
        return explain_system, (
            f"From article '{post.title}', explain: {selection[:500]}"
        )
```

## 选中提示气泡（Reader）

`Reader.jsx` 监听 `selectionchange` 事件，防抖 200ms。当前选区文字数 ≥ 5 且锚点落在 `.reader-body` 内 → 在 pet 头顶显示 `click pet to explain ↑`，2s 后淡出。pet 上的现有 `clawd-bubble` 样式复用（颜色用 `--accent`）。

实现：在 `App.jsx` 顶层用 `useState` 维护 `petHint`，传给 `<AsciiPet hint={petHint} />`；Reader 用 props/context 写入。

## 限流（3 层）

Redis key 模式：

| key                        | window     | default cap |
|----------------------------|------------|-------------|
| `rl:pet:ip:{ip}:1m`        | 60 s       | 6           |
| `rl:pet:ip:{ip}:1d`        | 86400 s    | 30          |
| `rl:pet:global:{YYYYMMDD}` | rollover   | 500         |

复用 `services/rate_limit.py` 的 `hit()`，但要扩出一个 `peek()` 来按层 short-circuit（任何一层命中即拒）。

被限流时返回 `200 OK` 携带 `{"quip": <random tired_line>, "source": "rate_limited"}`，避免触发前端 error UI。前端无差别地把 quip 显示出来。

`event_log`：`pet.summoned` 的 `meta` 增加 `{mode, provider, source}`，方便事后分析单次成本和命中率。

## 皮肤系统迁移

### 数据迁移

新建 `src/components/pet/species.js`：

```js
export const SPECIES = {
  // 18 from buddy-skin-editor (rarity assigned by us):
  duck:    { rarity: 'common',    color: '#f5d44c', frames: [...] },
  goose:   { rarity: 'common',    color: '#e8e8e8', frames: [...] },
  blob:    { rarity: 'common',    color: '#7dd3a4', frames: [...] },
  cat:     { rarity: 'common',    color: '#e0a96d', frames: [...] },
  rabbit:  { rarity: 'common',    color: '#f0d8e0', frames: [...] },
  penguin: { rarity: 'uncommon',  color: '#5c7ec4', frames: [...] },
  owl:     { rarity: 'uncommon',  color: '#a89060', frames: [...] },
  turtle:  { rarity: 'uncommon',  color: '#7da888', frames: [...] },
  capybara:{ rarity: 'uncommon',  color: '#d4a574', frames: [...] },
  mushroom:{ rarity: 'rare',      color: '#d05a5a', frames: [...] },
  ghost:   { rarity: 'rare',      color: '#c8c8e0', frames: [...] },
  snail:   { rarity: 'rare',      color: '#b89060', frames: [...] },
  cactus:  { rarity: 'rare',      color: '#7dbf8e', frames: [...] },
  chonk:   { rarity: 'rare',      color: '#c4a484', frames: [...] },
  octopus: { rarity: 'epic',      color: '#b89cf0', frames: [...] },
  jellyfish:{rarity: 'epic',      color: '#a4d4e8', frames: [...] },
  axolotl: { rarity: 'epic',      color: '#f0a4d4', frames: [...] },
  robot:   { rarity: 'epic',      color: '#7cc7f0', frames: [...] },
  dragon:  { rarity: 'legendary', color: '#ff7a5c', frames: [...] },

  // 4 hand-authored legendary rarities (drafted in implementation):
  phoenix: { rarity: 'legendary', color: '#ff9544', frames: [...] },
  fox:     { rarity: 'legendary', color: '#f08c5c', frames: [...] },
  shiba:   { rarity: 'legendary', color: '#e8a474', frames: [...] },
  mochi:   { rarity: 'legendary', color: '#fff0e8', frames: [...] },
};
```

旧 `BODY` 字典（5 个 `{L}{R}{M}` 角色）从 `AsciiPet.jsx` 删除，迁移期对老用户的 `localStorage.getItem('pet.body')` 做映射：旧值 `cat`/`dragon`/`octopus`/`robot`/`capybara` 直接命中新数据源里的同名 species（视觉会变，但名字保持），其它无效值回退到默认 `cat`。
```

### 状态表达

- 帧切换：3 帧 idle 循环；speed 由 state 决定（`thinking: 540ms` / `typing: 180ms` / `sleeping: 1600ms`）
- 眼字符替换 `{E}` → 按 state 映射（`idle: ·` / `thinking: °` / `happy: ✦` / `sleeping: -` / `error: ×` / `startled: ◉`）
- 浮层（不动 sprite）：`zzz`（sleeping）、`!`（startled / error）、`?`（thinking）等
- color 用 species 自带 + state tint 做 mix（`color-mix(in oklab, ${species.color} 70%, ${state.tint})`）

### 设置面板

`AsciiPet` 的 `pet-panel` 把 22 个 species 按 rarity 分组显示，每组一行，legendary 用金色边框标识。点选切换。

## 兜底 / 错误处理

| 情况                       | 行为                                                         |
|----------------------------|--------------------------------------------------------------|
| Provider 超时（5s）         | 走 fallback chain 下一家                                     |
| Provider 4xx               | 记 last_error 到 integrations 表，走下一家                   |
| Provider 5xx               | 记 last_error，走下一家                                      |
| 全部 provider 失败          | 返回 `random.choice(fallback_lines)`，`source="fallback"`    |
| 限流命中（任意层）          | 返回 `random.choice(tired_lines)`，`source="rate_limited"`   |
| `enabled=false`            | 直接走 fallback，不尝试任何 provider                          |
| `post_id` 不存在            | 降级到 `greet` mode                                          |

## 测试策略

### 后端

- `tests/services/test_pet_gateway.py`
  - 第 1 家成功 → 不调第 2 家
  - 第 1 家超时，第 2 家成功 → 返回第 2 家结果
  - 全部失败 → 返回 fallback，source="fallback"
  - 空 providers 列表 → 直接走 fallback
- `tests/services/test_pet_rate_limit.py`
  - 单层命中各自返回正确 source（`rate_limited`）
  - 限流命中时不调用任何 adapter（mock 验证 0 次调用）
- `tests/routers/public/test_pet_summon.py`
  - 3 种 mode prompt 拼接正确（用 mock gateway 捕获 system/user）
  - selection 截断到 max_context_chars
  - post_id 不存在时降级到 greet
  - 所有响应都是 200 OK（包括限流）
- `tests/routers/admin/test_integrations_zhipu.py`
  - PUT/GET 智谱 token，加密存储正确
  - 新厂商 ping 通后 `last_status="ok"`
- `tests/migrations/test_0008_round_trip.py`
  - upgrade 后能写入 zhipu/qwen/doubao
  - downgrade 后回到旧约束

### 前端

- `src/components/pet/__tests__/payload.test.js`（vitest）
  - `/p/abc` 无选中 → mode=comment, payload={post_id:'abc'}
  - `/p/abc` 选中 ≥5 字 → mode=explain, payload 含截断后的 selection
  - `/` → mode=greet
- `src/components/pet/__tests__/species.test.js`
  - 22 个 species 都能渲染，`{E}` 替换正确
  - rarity 分组数量正确（common/uncommon/rare/epic/legendary 各组非空）

## 实施分阶段

为了 PR 不爆，分 4 个 commit：

1. **backend gateway + migration**：alembic 0008、`pet_gateway.py`、3 个 adapter、扩 `PetConfig`、改 `routers/public/pet.py`、新 admin integrations 端点（zhipu/qwen/doubao 各一组 GET/PUT）。带后端全部测试。
2. **frontend payload + selection hint**：改 `AsciiPet.jsx` click handler，加 selection 监听；不动皮肤。带前端测试。
3. **species 数据迁移**：新建 `src/components/pet/species.js`，搬 18 个；改 `AsciiPet.jsx` 用新数据源 + `{E}` 单眼位 + state→eye-char 映射；删旧 `BODY` 字典；加 localStorage 旧值映射。
4. **4 个 legendary 手作**：phoenix / fox / shiba / mochi 的 ASCII 帧 + 接入设置面板分组渲染。

## Open questions（实施前再确认）

- 智谱 / 通义 / 豆包 的具体 endpoint 和 model id 实施前用 context7 拉最新文档确认，避免硬编码失效（这些 API 文档变更比较频繁）。
- 4 个 legendary buddy 的 ASCII 草稿在实施 step 4 时单独 review 一轮（不在本 spec 里画）。
