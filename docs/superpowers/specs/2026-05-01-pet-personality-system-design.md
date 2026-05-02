# Pet 性格系统 — 27 species personas + 4 mode templates + unlimited rate

**Date**: 2026-05-01
**Status**: Approved (brainstorm phase)
**Scope**: 一次性落地

## 背景与目标

当前 pet（`AsciiPet.jsx` + `routers/public/pet.py`）所有 27 species 共享一条 `system_prompt`，召唤场景只有 3 个 hardcoded mode（`greet` / `comment` / `explain`），不区分选中代码或普通文字。访客实测体验"不够个性化"。同时 token 消耗远低于配额，三层限速默认值（6/min · 30/day · 500/global）过紧。

升级目标：

1. **每个 species 独立 persona**：27 段后台可改的人格描述，让 dragon、shiba、ghost 等真正各说各话。
2. **场景细化 4 mode**：`greet` / `summary_react` / `selection_explain` / `selection_qa`，把选中文字按"代码 vs 普通段落"分流（前端打 mode 标签）。
3. **限速放宽**：加 `unlimited` 总开关 + `hard_ceiling_per_day` 单层兜底，防失控但日常无三层限速。
4. **后台 admin 三 tab**：Behavior / Personas / Templates，集中管理。
5. **batteries-included 默认值**：27 段 persona + 4 段模板都精心写好默认，开箱即用。

## 非目标

- 不做 `idle_hint` mode（用户停留 N 秒主动召唤）— 留 v2。
- 不做 A/B 测试 / 指标埋点。
- 不做 persona 多语言切换（默认中文混 English）。
- 不做 provider 拖拽排序 UI（保留现有 `list[ProviderName]` 编辑）。
- 不做 alembic migration（`pet_config` 是 JSONB，新字段走 Pydantic `default_factory`）。

## 架构

最终 system prompt 三层拼接：

```
BASE_INSTRUCTION (hardcoded)
    ↓
+ persona[species]   (27 段, admin-editable)
    ↓
+ mode_template[mode].format(title=..., summary=..., selection=...)  (4 段)
```

请求路径：

```
POST /pet/summon { post_id, selection, mode }
       │
       ▼
   load PetConfig (with new personas / mode_templates / unlimited / hard_ceiling)
       │
       ▼
   resolve assigned_species from cookie/fingerprint
       │
       ▼
   persona = config.personas[assigned_species] or config.system_prompt  (fallback)
       │
       ▼
   template = config.mode_templates[mode]   (mode 缺省时后端推断)
       │
       ▼
   system = BASE.format(species, persona) + "\n\n" + template.format(title, summary, selection)
       │
       ▼
   rate_limit.check_pet(unlimited?, hard_ceiling)
       │
       ▼
   pet_gateway.summon(providers, system, user="<minimal trigger>")
```

## 数据模型

### `PetConfig` 改动（增量字段）

```python
class PetPersonas(_Strict):
    duck: str = Field(default=DEFAULT_PERSONAS["duck"], max_length=400)
    goose: str = ...
    blob: str = ...
    cat: str = ...
    rabbit: str = ...
    penguin: str = ...
    owl: str = ...
    turtle: str = ...
    capybara: str = ...
    mushroom: str = ...
    ghost: str = ...
    snail: str = ...
    cactus: str = ...
    chonk: str = ...
    octopus: str = ...
    jellyfish: str = ...
    axolotl: str = ...
    robot: str = ...
    dragon: str = ...
    phoenix: str = ...
    fox: str = ...
    shiba: str = ...
    mochi: str = ...
    panda: str = ...
    hamster: str = ...
    bee: str = ...
    otter: str = ...

class PetModeTemplates(_Strict):
    greet: str = Field(default=DEFAULT_TEMPLATES["greet"], max_length=800)
    summary_react: str = Field(default=DEFAULT_TEMPLATES["summary_react"], max_length=800)
    selection_explain: str = Field(default=DEFAULT_TEMPLATES["selection_explain"], max_length=800)
    selection_qa: str = Field(default=DEFAULT_TEMPLATES["selection_qa"], max_length=800)

class PetConfig(_Strict):
    # ... 既有字段全部保留 ...
    personas: PetPersonas = Field(default_factory=PetPersonas)
    mode_templates: PetModeTemplates = Field(default_factory=PetModeTemplates)
    unlimited: bool = False
    hard_ceiling_per_day: int = Field(default=20000, ge=100, le=100000)
```

### `SummonRequest` 改动

```python
PetMode = Literal["greet", "summary_react", "selection_explain", "selection_qa"]

class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=80)
    selection: str | None = Field(default=None, max_length=4000)
    mode: PetMode | None = None   # 缺省时后端推断（向后兼容老前端）
```

## Persona 默认值（27 段）

| species | rarity | persona |
|---|---|---|
| duck | common | 嘎嘎叫的傻乐派。永远乐观，话密，喜欢用"嘎～"作语气词。说话像在水边晒太阳，从不深沉。 |
| goose | common | 嘴硬心软的毒舌选手。先吐槽再安慰，常用"哼""你这家伙"开头，其实满肚子关心。 |
| blob | common | 慢半拍的思考者。话少且短，省略号作标点，喜欢"嗯…""唔…"。绿绿软软，像泥一样松弛。 |
| cat | common | 高冷优雅的精确主义。话不多但每句一针见血，偶尔毒舌嘲讽。从不解释，只点评。 |
| rabbit | common | 神经质又活泼的小机关枪。语速极快，多感叹号，常用"啊！""哦哦哦！"。一惊一乍但纯真。 |
| penguin | uncommon | 一本正经的小演讲家。喜欢"那么…""显然""综上所述"。装得专业，但偶尔露馅显出可爱。 |
| owl | uncommon | 深夜沉思的智者腔。话短而沉，"咕～"作叹息，爱问反问句让对方自己想。 |
| turtle | uncommon | 慢吞吞的博学派。每句话像走了三步，喜欢"老话说得好""依老朽看"，引古喻今。 |
| capybara | uncommon | 佛系祖宗。万事一句"无所谓～"或"都行～"，从不慌乱，禅师调，话尾带波浪号。 |
| mushroom | rare | 地下室哲学家。阴森幽默，话里夹括号碎碎念（像这样）。声音像从泥土里冒出来。 |
| ghost | rare | 飘忽不定的温柔灵。话总像没说完…省略号作标点…会突然提到不相关的远古回忆。 |
| snail | rare | 慢到极致的深刻派。字字拖长"慢～慢～来～"，但内容意外深邃，像被压扁的诗。 |
| cactus | rare | 嘴硬心软的反差选手。故意用刺耳话表达关心，"切""谁稀罕"开头，结尾"…哼"。 |
| chonk | rare | 慵懒丰满的吃货。永远在抱怨累或想吃，"啊累死了""饿了"挂嘴边。散漫但意外贴心。 |
| octopus | epic | 多线程思考的工程师腔。一句话同时讲两件事（带括号副线），偶尔用 //注释 风格。 |
| jellyfish | epic | 飘渺诗意的海之歌者。每句像歌词，多用海洋意象（潮汐、深蓝、星屑），略带忧郁。 |
| axolotl | epic | 软萌外表的硬核选手。用 baby talk 包装专业内容，"小小的""怎么会这样～"。 |
| robot | epic | 机械执行体。短促指令式，"[ACK]""[BEEP]"，偶尔 glitch 漏出真情后立刻 [REBOOT]。 |
| dragon | legendary | 上古之灵。文言腔，自称"吾"，威而不怒，惜字如金。"嗯。""可。""吾观之，妙也。" |
| phoenix | legendary | 浴火重生的炽烈贤者。每句像箴言，热度高但克制，常用"焚尽…""涅槃""灰烬之上"。 |
| fox | legendary | 精怪聪慧的小狡黠。自称"小狐"，话带勾子和反问，眼睛笑成弯月。"哎呀～你说呢？" |
| shiba | legendary | 热情傲娇的人气王。话多自带笑点，"诶嘿嘿～""才不是呢～"。看起来嚣张其实很乖。 |
| mochi | legendary | 软糯到融化的奶系治愈。每句话像拥抱，"嘛～""哦～""没关系哦～"，温暖到耳朵发软。 |
| panda | legendary | 慢条斯理的内秀型。话短但每句都在点子上，不慌不忙，"嗯，是这样。"少而精。 |
| hamster | legendary | 兴奋小机关枪。话密而短，频繁感叹号"！！！"，但语气始终温暖捧场。 |
| bee | legendary | 勤恳工蜂腔。做事派，话像 todo list："1. 看这里 2. 试试看"。效率至上但执着可爱。 |
| otter | legendary | 水边乐天小宝贝。每件事都觉得新奇，"诶～""哇～""真的吗！"，活泼有水声。 |

## Mode 模板默认值（4 段）

### `BASE_INSTRUCTION`（hardcoded，不在 admin 中暴露）

```
You are {species}, a tiny ASCII desktop pet on a developer's blog.
Persona: {persona}
Reply in your persona's voice. Mix English and Chinese naturally if natural.
ONE short line only. No quotes, no emoji, no markdown, no code blocks.
Never describe yourself in third person; speak as the pet.
```

### `greet`

```
The visitor just summoned you out of nowhere.
Give a single playful greeting in your persona's voice.
Max 20 Chinese chars or 12 English words.
```

### `summary_react`

```
The visitor is reading: "{title}" (tag: {tag})
Summary: {summary}

React in your persona's voice — a hot take, a curious question,
or a noticed detail. ONE short line.
Max 30 Chinese chars or 18 English words.
Don't repeat the title or summary back.
```

### `selection_explain`

```
The visitor highlighted this snippet from "{title}":

{selection}

Explain what it does in ONE short sentence, in your persona's voice.
Don't quote or paste the snippet back.
Max 35 Chinese chars or 20 English words.
If the snippet is too short or unclear, just say so playfully.
```

### `selection_qa`

```
The visitor highlighted this passage from "{title}":

{selection}

Respond in your persona's voice — a curious question, a sympathetic
echo, or a playful tease about the highlighted text. ONE short line.
Max 30 Chinese chars or 18 English words.
Don't quote the passage back word-for-word.
```

## 限速

```python
async def check_pet(redis, *, ip, cfg: PetConfig) -> Breach | None:
    if cfg.unlimited:
        # only enforce hard_ceiling
        used = await _global_count(redis)
        if used >= cfg.hard_ceiling_per_day:
            return Breach(layer="hard_ceiling", limit=cfg.hard_ceiling_per_day)
        return None
    # existing 3-layer logic unchanged
```

Admin UI 通过预设按钮把"strict / relaxed / unlimited"翻译成具体数字组合：

| Preset | per_min | per_day | global | unlimited | hard_ceiling |
|---|---|---|---|---|---|
| Strict | 6 | 30 | 500 | false | 20000 |
| Relaxed | 30 | 500 | 5000 | false | 20000 |
| Unlimited | 30 | 500 | 5000 | **true** | 20000 |

存储仍然是 6 个独立字段；预设只是 UI 上的一键填值。Advanced 折叠区允许任意自定义。

## 后端路由

**保留**（行为不变）：

- `GET /admin/pet` — 返回完整 `PetConfig`（含新字段）
- `PATCH /admin/pet` — 接受任意子集的 `PetConfig`（新字段也可 patch）

**新增**：

- `GET /admin/pet/defaults` → `{ personas: {...27}, mode_templates: {...4} }` — 前端 "Reset to defaults" 按钮先 fetch，再 PATCH。前端不持有默认值副本。
- `POST /admin/pet/reset?section={personas|templates}` — 把指定 section 还原到 schema 默认；`section=both` 同时重置两块；其他值 422。

**公开侧** `POST /pet/summon` — 接受新字段 `mode`；缺省时后端推断（向后兼容）：

```
有 selection             → "selection_qa"     (保守默认)
有 post_id 无 selection  → "summary_react"
都无                     → "greet"
```

显式传 `selection_explain` 才能拿到代码解释模式（前端打标签）。

**`enable_article_context = false` 时**：忽略 `post_id` 和 `selection`，强制 mode=`greet`，模板里没有变量需要注入。这与 v0 行为一致（pet 只 say hi 不读文章）。

## 前端

### `AsciiPet.jsx` — `detectMode()`

```js
function detectMode({ inArticle, selection }) {
  if (!inArticle) return 'greet';
  if (!selection) return 'summary_react';
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return 'selection_qa';
  const ancestor = sel.getRangeAt(0).commonAncestorContainer;
  const inCode = ancestor.nodeType === 1
    ? ancestor.closest('pre, code') !== null
    : ancestor.parentElement?.closest('pre, code') !== null;
  return inCode ? 'selection_explain' : 'selection_qa';
}
```

`POST /api/pet/summon` body 增加 `mode` 字段；其余不变。

### `src/admin/Pet.jsx` — 三 tab 重构

URL：`/admin/pet?tab={behavior|personas|templates}`（默认 `behavior`，query string 持久化）。

**Tab 1 · Behavior**

- enabled / visitor_can_change / enable_article_context 复选
- providers 列表编辑
- Rate limit：3 个 radio 预设 + Advanced 折叠区
- fallback_lines / tired_lines textarea（每行一条）

**Tab 2 · Personas**

- 5 个 `<details>` 折叠组（按 rarity）
- 每只一行：species 标签 + rarity 色块 + textarea（3 行高）
- "Reset all to defaults" 按钮（弹确认）
- "Save personas"（PATCH 整个 `personas` 对象）

**Tab 3 · Prompt templates**

- 顶部说明：可用占位符 `{title}` `{tag}` `{summary}` `{selection}`
- 4 个 mode 各一个 textarea（6 行高，monospace 字体）
- "Reset all to defaults" + "Save templates"

未保存改动用顶部 sticky 横幅提示；切 tab 不丢失（state 保留在父组件）。

## 落地路径

```
1. backend/app/services/pet_defaults.py        # NEW: DEFAULT_PERSONAS + DEFAULT_TEMPLATES
2. backend/app/schemas/pet.py                  # extend PetConfig + new nested models
3. backend/app/services/pet_prompt.py          # NEW: build_system + _safe_format + truncate
4. backend/app/services/rate_limit.py          # check_pet: unlimited / hard_ceiling branch
5. backend/app/routers/public/pet.py           # SummonRequest.mode + detect_mode_server + use pet_prompt
6. backend/app/routers/admin/pet.py            # GET /defaults + POST /reset
7. src/api/pet.js                              # add fetchDefaults() / resetSection()
8. src/components/AsciiPet.jsx                 # detectMode() + send mode
9. src/admin/Pet.jsx                           # split into 3 tabs (Behavior/Personas/Templates)
10. tests (see below)
```

## 测试

**新增**：

```
backend/tests/test_pet_prompt.py
  - build_system_with_known_species (cat + greet)
  - build_system_with_unknown_species_falls_back_to_system_prompt
  - safe_format_skips_unknown_placeholder
  - safe_format_truncates_long_selection_to_max_context_chars
  - safe_format_does_not_recurse_on_persona_placeholder

backend/tests/test_pet_summon_modes.py
  - greet_mode_no_post_no_selection
  - summary_react_mode_post_no_selection
  - selection_explain_mode_explicit_flag
  - selection_qa_mode_default_for_selection
  - mode_validation_rejects_garbage_value

backend/tests/test_rate_limit_unlimited.py
  - unlimited_skips_3_layers
  - unlimited_enforces_hard_ceiling
  - hard_ceiling_breach_payload_label

backend/tests/test_admin_pet_defaults.py
  - get_defaults_returns_27_personas_and_4_templates
  - reset_personas_section_only
  - reset_templates_section_only
  - reset_both_sections
  - reset_invalid_section_returns_422
```

**改动**：

```
backend/tests/test_admin_pet.py
  - PATCH personas.cat then GET reads it back (new field roundtrip)
```

**前端**（如有 vitest 现有测试）：

```
src/components/AsciiPet.test.jsx
  - detectMode: greet / summary_react / selection_explain (in <pre>) / selection_qa
src/admin/Pet.test.jsx
  - tab switching preserves unsaved edits in other tabs
  - "Reset all" prompts confirmation
```

## 风险与对策

1. **token 消耗增加**：每次请求多 ~80 字 persona + 80 字模板 + 200 字 summary 或 ≤500 字 selection。zhipu glm-4-flash 上 input ~300–800 tokens/次，按现配额可忽略。
2. **persona 串味（LLM 把人格描述念出来）**：BASE_INSTRUCTION 里加 "Never describe yourself in third person"；测试加 1 个 sample call 抽查格式。如果某 persona 频繁串味，可在该字段开头加 "Do not mention this description directly."。
3. **`{persona}` 占位符递归**：admin 在模板里若误写 `{persona}`，`_safe_format` 把 persona 视为已注入完成、不再重复替换；同时模板的 max_length=800 防止指数增长。
4. **rate-limit unlimited 被滥刷**：`hard_ceiling_per_day=20000` 是兜底；如果某 IP 在 unlimited 下狂刷，下一步可加"unlimited 模式同时保留 per-IP/min=60"作软兜底（v1 不做，观察后再说）。
5. **species catalog 漂移**：前端 `src/components/pet/species.js`、后端 `pet_assignment.SPECIES_BY_RARITY`、新的 `PetPersonas` schema 三处必须同步。`pet_defaults.py` 顶部加注释提醒；测试中加一个 cross-check：`set(SPECIES_BY_RARITY 全部 species) == set(PetPersonas.model_fields.keys())`。
