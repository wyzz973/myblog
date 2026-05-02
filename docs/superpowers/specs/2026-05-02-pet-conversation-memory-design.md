# Pet 对话记忆系统 — Redis 短期上下文 + Postgres 永久归档

**Date**: 2026-05-02
**Status**: Approved (brainstorm phase)
**Scope**: 一次性落地

## 背景与目标

当前 pet (`AsciiPet.jsx` + `routers/public/pet.py` + `pet_gateway.py`) 每次召唤都是无状态的：访客点 pet 三次得到三段毫无关联的回复。LLM 不知道"这是同一个访客"，更不知道"刚才聊了什么"。

升级目标：

1. **跨页连续对话**：以 `pet_id` cookie 标识的同一访客的所有 pet 召唤共享 conversation context；新 token 注入到 LLM 的 messages 数组。
2. **2 小时 sliding TTL · 10 轮窗口**：上下文活跃 2h 自动延续，离开 2h 即过期；最多保留最近 10 轮 user/assistant pair。
3. **永久持久化全量历史**：每次召唤的 (system_prompt, prior_turns, mode, post info, selection, reply, source) 写入新 `pet_message` 表，无 retention 上限。
4. **Admin 后台浏览**：新 conversations tab 按 visitor_hash 分组显示对话历史，可查看完整 message timeline，可删除单个 visitor 的全部记录。
5. **隐私缓冲**：visitor 用 `ip_hash(ip)[:16]` 单向匿名化；不存原始 IP/UA/cookie。

## 非目标

- 不做访客自助"删除我的数据"按钮（v2 候选）。
- 不做"开启新会话"显式按钮（2h sliding 已足够自然）。
- 不做按 post_id 隔离的 sub-conversation（A 方案：跨页连续是核心心智）。
- 不做 90/180 天自动 retention 清理（B 方案：永久保留；DB 体积可控）。
- 不做 like_salt 旋转后的 visitor_hash 迁移工具（运维罕见）。
- 不做 prior_turns 的 LLM 重试（gateway 现有 provider fallback 已够用）。

## 已知隐私权衡 (acknowledged)

- `pet_message.selection` 字段保留访客在文章里选中的原文文本，永久保留。
- `pet_message.reply` 保留 LLM 的完整回复（少量包含 selection 引用）。
- `visitor_hash` 是单向 HMAC，无法反推原 IP，但在 `like_salt` 不旋转的前提下对同一 (IP, UA) 稳定。
- 数据落地于 Postgres，加密静态依赖部署层（dev 环境无加密）。
- 个人博客流量级别下，total DB footprint 估算 < 50 MB/year，不引入容量风险。

如果未来流量上规模或开放注册，应优先做：(a) 访客自助删除入口；(b) 自动 retention（保留 1 年）；(c) `selection` 字段加 redaction 选项。

## 架构

### 数据流

```
visitor clicks pet
        │
        ▼
POST /pet/summon/stream  { post_id, selection, mode? }
        │
        ▼
1. 解析 cookie → assigned_species (existing pet_assignment.verify_cookie)
2. 计算 visitor_hash = ip_hash(ip)[:16]
3. rate_limit.check_pet (existing)
4. pet_context.load(redis, visitor_hash)        ← 拿 prior turns
5. pet_prompt.build_system(...)                  (existing, unchanged)
6. pet_prompt.build_messages(prior, current_turn)  ← NEW
        │
        ▼
gateway.summon_stream(system, messages)         ← 升级签名
        │ chunk events
        ▼ (SSE)
front-end accumulates → bubble streams
        │
        ▼ (after stream ends, fire-and-forget)
async_task:
    - pet_context.append(redis, visitor_hash, user_turn, assistant_reply)
    - INSERT INTO pet_message (...)
```

### 两层存储

| 层 | 用途 | TTL | Storage |
|---|---|---|---|
| **Hot** | LLM 注入用的最近 10 轮 | 2h sliding | Redis list `pet:ctx:<visitor_hash>`，cap 20 entries |
| **Cold** | 完整归档，admin 浏览 | 永久 | Postgres `pet_message` 表 |

**关键设计点**：Redis key 用 `visitor_hash`（不用 `pet_id` cookie 值），因为：
- visitor_hash 是 stable per-(IP, UA)
- admin DELETE 可一次性清 Redis + DB（同一 key 维度）
- pet_id 仅作为 species 分配的 cookie，不参与对话身份

## 数据模型

### Postgres `pet_message` 表

```sql
CREATE TABLE pet_message (
    id              BIGSERIAL PRIMARY KEY,
    visitor_hash    VARCHAR(16) NOT NULL,
    species         VARCHAR(32) NOT NULL,
    mode            VARCHAR(32) NOT NULL,          -- includes 'rate_limited'/'fallback' as terminal sources
    post_id         VARCHAR(80),
    title           VARCHAR(200),
    tag_slug        VARCHAR(40),
    summary         TEXT,
    selection       TEXT,
    system_prompt   TEXT NOT NULL,
    prior_turns     JSONB NOT NULL DEFAULT '[]',
    reply           TEXT NOT NULL,
    source          VARCHAR(32) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_pet_message_visitor_hash_created
    ON pet_message (visitor_hash, created_at DESC);
CREATE INDEX ix_pet_message_created_at
    ON pet_message (created_at DESC);
```

**Field notes**:
- `title / tag_slug / summary` 是 denormalized snapshot — post 删/改后历史记录仍正确。无 FK。
- `prior_turns JSONB` shape: list of `{"role": "user"|"assistant", "content": "...", "mode": "...", "post_id": "..."}`. 完整可重放 LLM 输入。
- `mode` 包含 `rate_limited` / `fallback` 这两个非真实模式的 sentinel，便于分析。

### Redis layout

```
Key:    pet:ctx:<visitor_hash>
Type:   list
Member: JSON-encoded turn  {"role":"...","content":"...","mode":"...","post_id":"..."}
Order:  newest first (LPUSH)
TTL:    7200s sliding
Cap:    20 entries (10 user + 10 assistant)
```

操作语义：
- `load`: `LRANGE 0 19` → reverse → JSON parse each → return chronological list
- `append(user_turn, assistant_reply)`:
  ```
  pipeline:
    LPUSH key json(assistant_turn)
    LPUSH key json(user_turn)
    LTRIM key 0 19
    EXPIRE key 7200
  ```

## 接口形状

### `pet_gateway.summon_stream` 签名升级

**Before**:
```python
async def summon_stream(
    *, providers, secrets, system: str, user: str,
    fallback_lines, timeout_per_call=30.0,
) -> AsyncIterator[dict]
```

**After**:
```python
async def summon_stream(
    *, providers, secrets, system: str,
    messages: list[dict],  # [{"role":"user"|"assistant","content":"..."}, ...]
    fallback_lines, timeout_per_call=30.0,
) -> AsyncIterator[dict]
```

**Adapter changes**:
- `openai_compat.chat_stream(..., messages=[...])`: `body["messages"] = [{"role":"system","content":system}, *messages]`
- `anthropic.chat_stream(..., messages=[...])`: pass `messages=messages` directly to SDK

**Backwards compat**: existing `summon` (non-streaming) keeps `user: str` API and wraps to `messages=[{"role":"user","content":user}]`. Existing `chat` adapter functions unchanged.

### New service: `pet_context.py`

```python
# backend/app/services/pet_context.py

from collections.abc import Sequence
from redis.asyncio import Redis

KEY_PREFIX = "pet:ctx:"
DEFAULT_MAX_TURNS = 10
DEFAULT_TTL_SEC = 7200


def _key(visitor_hash: str) -> str:
    return f"{KEY_PREFIX}{visitor_hash}"


async def load(
    redis: Redis,
    visitor_hash: str,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> list[dict]:
    """Return prior turns oldest-first. Empty list on miss/error."""


async def append(
    redis: Redis,
    visitor_hash: str,
    *,
    user_turn: dict,
    assistant_turn: dict,
    max_turns: int = DEFAULT_MAX_TURNS,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> None:
    """Atomic LPUSH user+assistant + LTRIM cap + EXPIRE."""


async def clear(redis: Redis, visitor_hash: str) -> None:
    """DEL key — used by admin DELETE."""
```

`max_turns` and `ttl_sec` exposed as `PetConfig` fields:

```python
class PetConfig(_Strict):
    # ... existing ...
    context_window_turns: int = Field(default=10, ge=1, le=50)
    context_ttl_seconds: int = Field(default=7200, ge=60, le=86400)
```

### New `pet_prompt.build_messages`

```python
def build_messages(
    cfg: PetConfig,
    *,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
    prior: Sequence[dict],
) -> list[dict]:
    """Build the messages array passed to the gateway.

    Returns: [*prior, current_user_turn] where current_user_turn is a
    scene tag describing what the visitor just did.
    """
```

**Scene tag formats** (the `content` field of the user turn):

| mode | content template |
|---|---|
| `greet` | `(visitor tapped on you)` |
| `summary_react` | `(visitor reading "{title}", tag: {tag})` |
| `selection_explain` | `(visitor highlighted code from "{title}"): {selection}` |
| `selection_qa` | `(visitor highlighted from "{title}"): {selection}` |

`build_system` keeps its existing signature unchanged. System prompt stays focused on persona + current-mode framing; messages array carries the dialogue history.

### Public endpoint contract (no breaking change)

`POST /pet/summon/stream` — same request body, same SSE event types. Internally:

```
1. cfg = _load_pet_config(s)
2. visitor_hash = ip_hash(client_ip)[:16]
3. rate_limit check (existing)
4. mode + post resolution (existing)
5. assigned = pet_assignment.verify_cookie(...) or assign_species(...)
6. system = pet_prompt.build_system(cfg, ...)
7. prior = await pet_context.load(redis, visitor_hash, max_turns=cfg.context_window_turns)
8. messages = pet_prompt.build_messages(cfg, mode=..., ..., prior=prior)
9. (stream) gateway.summon_stream(system=system, messages=messages, ...)
10. After stream completes (background task with fresh AsyncSessionLocal):
    - pet_context.append(redis, visitor_hash, user_turn=current, assistant_turn={"role":"assistant","content": full_reply})
    - INSERT INTO pet_message (...)
```

**Failure handling**:
- `pet_context.load` raises (Redis down) → fall back to empty `prior`; pet is "fresh" this turn.
- `pet_context.append` raises → log warning; this turn lost from memory.
- DB INSERT raises → log warning; archive lost but visitor already got their reply.
- Visitor never sees backend persistence failures.

### Admin endpoints (new)

```
GET /api/admin/pet/conversations
    ?cursor=<base64-encoded last_msg_at|visitor_hash>
    &limit=50
    &species=cat        (optional filter)
    &since=<ISO date>   (optional filter)

→ {
    items: [
      {
        visitor_hash: "9c1f4e2a...",
        species: "cat",
        last_msg_at: "2026-05-02T13:08:00Z",
        message_count: 12,
        last_reply_preview: "嗯，这段闭包写得有意思——确实漏了..."
      },
      ...
    ],
    next_cursor: "..."
  }

GET /api/admin/pet/conversations/{visitor_hash}
    ?cursor=<message id>
    &limit=100

→ {
    items: [pet_message rows for this visitor, oldest first],
    next_cursor: "..."
  }

DELETE /api/admin/pet/conversations/{visitor_hash}

→ 204 No Content
   - DELETE FROM pet_message WHERE visitor_hash=$1
   - pet_context.clear(redis, visitor_hash)  (best-effort; ignore Redis errors)
```

All three require `current_admin`; DELETE additionally requires `require_scope("write")`.

The list query is a single SQL with `GROUP BY visitor_hash`:

```sql
SELECT
    visitor_hash,
    (array_agg(species ORDER BY created_at DESC))[1] AS species,
    MAX(created_at) AS last_msg_at,
    COUNT(*) AS message_count,
    (array_agg(LEFT(reply, 80) ORDER BY created_at DESC))[1] AS last_reply_preview
FROM pet_message
WHERE [filters]
GROUP BY visitor_hash
ORDER BY last_msg_at DESC
LIMIT $1;
```

Cursor pagination uses `(last_msg_at, visitor_hash)` to break ties; index `(visitor_hash, created_at DESC)` supports the per-visitor detail; index `(created_at DESC)` supports the global timeline.

## Admin UI

**Tab structure** (`/admin/pet?tab=conversations`):

```
┌─ Pet conversations · 152 visitors · 1,847 messages ─────────────────┐
│                                                                       │
│ search:  [_________________]  species: [all ▾]  last: [7d ▾]          │
│                                                                       │
│ ┌─────────────────────────────────────────────────────────────────┐  │
│ │ 9c1f4e2a... · cat       · 12 msgs · 2h ago                     │  │
│ │ "嗯，这段闭包写得有意思——确实漏了 cleanup。"                    │  │
│ ├─────────────────────────────────────────────────────────────────┤  │
│ │ 3a02bf81... · dragon    · 47 msgs · 5h ago                     │  │
│ │ "吾观此处 race condition，妙也。"                                │  │
│ ├─────────────────────────────────────────────────────────────────┤  │
│ │ ...                                                             │  │
│ └─────────────────────────────────────────────────────────────────┘  │
│                                                       [load more]    │
└──────────────────────────────────────────────────────────────────────┘
```

**Detail view** (`/admin/pet/conversations/<visitor_hash>`):

```
┌─ Conversation · 9c1f4e2a... · cat · 12 messages ──[delete all]──────┐
│                                                                       │
│ 2026-05-02 13:08  greet  /                                            │
│ 👤 (visitor tapped on you)                                            │
│ 🐱 召唤我只需轻敲屏幕，倒也算识趣。                                    │
│ ▸ debug                                                               │
│                                                                       │
│ 2026-05-02 13:09  summary_react  /p/hello                             │
│ 👤 (visitor reading "Hello", tag: devtools)                           │
│ 🐱 这篇主题居然把 useEffect 讲得像猫打哈欠。                            │
│                                                                       │
│ ...                                                                   │
│                                              [load older messages]    │
└──────────────────────────────────────────────────────────────────────┘
```

`▸ debug` 折叠区展示 `system_prompt` 和 `prior_turns`（默认收起）。

Delete confirms with native `confirm()`; redirects back to list on success.

## 落地路径

```
1. backend/app/models/pet_message.py        # NEW: SQLAlchemy model
2. backend/migrations/versions/<rev>_add_pet_message.py  # NEW: alembic migration
3. backend/app/schemas/pet.py               # add context_window_turns, context_ttl_seconds
4. backend/app/services/pet_context.py      # NEW: load / append / clear
5. backend/app/services/pet_prompt.py       # add build_messages
6. backend/app/services/pet_adapters/openai_compat.py  # chat_stream accepts messages
7. backend/app/services/pet_adapters/anthropic.py      # chat_stream accepts messages
8. backend/app/services/pet_gateway.py      # summon_stream upgraded signature; legacy summon wraps
9. backend/app/routers/public/pet.py        # call build_messages, append context, archive
10. backend/app/routers/admin/pet.py        # NEW: 3 conversations endpoints
11. src/api/pet.js                          # listConversations, getConversation, deleteConversation
12. src/admin/pet/PetConversations.jsx      # NEW list component
13. src/admin/pet/PetConversationDetail.jsx # NEW detail component
14. src/admin/Pet.jsx                       # add 'conversations' tab + route
15. tests (per Test Matrix below)
```

## 测试矩阵

**新增 backend tests**:

```
test_pet_context.py
  - load_returns_empty_when_no_history
  - load_returns_chronological_order_after_lpush
  - append_caps_at_2x_max_turns
  - append_resets_ttl_on_each_call
  - append_with_max_turns_5_keeps_only_last_5_pairs
  - clear_deletes_key

test_pet_message_model.py
  - insert_pet_message_basic_roundtrip
  - prior_turns_jsonb_roundtrip
  - selection_can_be_null
  - title_summary_tag_can_be_null

test_pet_prompt_messages.py
  - build_messages_with_empty_prior_yields_one_user_turn
  - build_messages_includes_scene_tag_for_each_mode
  - selection_truncated_to_max_context_chars
  - prior_turns_passed_through_unchanged

test_pet_summon_stream_history.py (extends existing test_pet_summon_modes)
  - first_summon_with_no_history_sends_only_current_turn
  - second_summon_includes_first_turns_assistant_reply_in_messages
  - rate_limited_does_not_pollute_history
  - history_persists_to_pet_message_after_stream
  - disabled_pet_skips_history_write
  - cross_visitor_isolation_via_visitor_hash

test_admin_pet_conversations.py
  - get_conversations_groups_by_visitor_hash
  - get_conversations_pagination_via_cursor
  - get_conversations_filter_by_species
  - get_conversations_filter_by_since
  - get_conversation_detail_returns_messages_oldest_first
  - delete_conversation_removes_db_rows
  - delete_conversation_clears_redis_ctx
  - delete_returns_204_for_nonexistent_visitor (idempotent)
```

**修改的 backend tests**:

```
test_pet_gateway.py
  - rename `user` → `messages`; existing 1-turn tests wrap to single message
test_pet_summon_modes.py
  - update mocks to expect messages array
test_pet_adapter_openai_compat.py
  - add messages-array assertion
test_pet_adapter_anthropic.py
  - add messages-array assertion
```

**新增 frontend tests**:

```
src/admin/pet/PetConversations.test.jsx
  - list_renders_grouped_visitors
  - clicking_row_navigates_to_detail
  - empty_state_renders_when_no_conversations
src/admin/pet/PetConversationDetail.test.jsx
  - messages_render_oldest_first
  - delete_button_prompts_confirm_then_calls_api
```

## 风险点

1. **Redis 故障降级**：Redis 不可达 → `pet_context.load` 返回 `[]` → pet 当成首次互动；DB 写仍照常进行（archive 不依赖 Redis）。`pet_context.append` 失败 → log warning，下次召唤丢这一轮记忆。可接受（Redis 是 cache）。

2. **DB 体积增长**：永久保留意味着会持续增长。估算上限按个人博客流量级（< 50MB/year）完全可承受。如果未来扩量，加 `prune_old_pet_messages` ARQ cron（保留 1 年）。已在非目标里明确推到 v2。

3. **Token 成本**：10 轮窗口 × ~80 字 ≈ 800 input tokens/次（额外 ~400 tokens vs 现状）。zhipu glm-4-flash 上一次 ~0.001 RMB，可忽略。

4. **List 视图 N+1**：admin 列表用 `GROUP BY visitor_hash + array_agg + MAX` 单查询完成。索引 `(visitor_hash, created_at DESC)` 支撑详情，`(created_at DESC)` 支撑全局过滤。

5. **隐私 footprint**：见上方"已知隐私权衡"。落地时 spec 同步加一行 README 提示部署者需了解此项（避免无意识接受）。

6. **Streaming 失败的 archive**：mid-stream 失败时，gateway 会发 `done` event 保留已收到的 partial（现有逻辑）。partial reply 仍写入 pet_message。重试不在本轮范围。

7. **like_salt 旋转**：旋转后 visitor_hash 全部变化，旧记录"找不到当事人"但 admin 仍可看（按 hash 索引）。运维罕见场景；不做迁移。

## 不变量

- `pet_id` cookie 仍然只用于 species 分配，不参与对话身份。
- `visitor_hash` 用于：rate limit key 后缀、Redis ctx key、pet_message 主键的 group-by 字段。
- `cfg.enable_article_context = false`：强制 mode=greet，post_id/selection 全部丢；prior_turns 仍然加载并注入（visitor 有连续记忆，只是当下场景空）。

### Sentinel-mode archiving rules

不同终端 source 的归档行为不同，意图：admin 看到所有访客互动以便分析，但 LLM 不被 canned 回复污染上下文。

| source | pet_message 写入 | Redis ctx 写入 | EventLog |
|---|---|---|---|
| `<provider>` (zhipu/anthropic/...) | ✓ mode=actual | ✓ user + assistant pair | ✓ existing |
| `rate_limited` | ✓ mode='rate_limited', reply=canned tired_line | ✗ | ✓ existing |
| `fallback` (LLM disabled / no providers / all providers failed) | ✓ mode=actual, source='fallback', reply=canned fallback_line | ✗ | ✓ existing |

理由：
- 写 pet_message 让 admin 能完整追踪 "这个 visitor 被限流了 / pet 当时是关闭状态"。
- 不写 Redis ctx 让下次召唤的 LLM 看到的是"上次说过的真话"，而不是 "pet 累了…" 这种 canned 文本被当作 assistant 之前的发言。
