# Admin Console — Frontend-Driven Rebuild PRD

| | |
|---|---|
| **Date** | 2026-05-05 |
| **Status** | Draft, source of truth for the rebuild |
| **Author** | Claude (under @sd3 direction) |
| **Stakeholder** | @sd3 — sole admin, sole content owner |
| **Scope** | Re-derive the admin console's information architecture, screens, and workflows from what the public site actually surfaces. Replace ad-hoc DB-table editors with task-oriented modules. |

This PRD is **not** a backlog of "what columns to put on which page". It is a top-down audit of the public site, followed by a reverse-engineered model of what a single owner needs to *do* to keep that site alive. The implementation plan in `docs/superpowers/plans/2026-05-05-admin-frontend-driven-task-index.md` decomposes these capabilities into shippable tasks.

---

## 0. Vocabulary

- **Owned content** — long-term editorial state the owner curates (posts, projects, profile, theme, pet templates).
- **Visitor-derived state** — data captured from visitors that the owner observes / moderates (comments, likes, hits, pet conversations, pet usage).
- **System state** — auth + integrations + tokens + danger ops; required for the site to keep running.
- **Workflow** — a multi-step task an owner does on a recurring cadence (e.g., "publish a draft", "moderate the comment queue", "sync GitHub", "rotate API keys"). The admin should be organized around these, not around tables.

---

## 1. Frontend page map

The public app is one Vite + React SPA mounted at `/*` (`src/main.jsx`). `src/App.jsx` does its own URL switching between two views. Every page also mounts `TopBar`, `Palette`, `AsciiPet`, `Konami`, and a footer.

### 1.1 Route `/` — terminal index (HomeA)

| # | Region | Component | Backing API | Owned vs derived |
|---|--------|-----------|-------------|------------------|
| topbar | brand, nav, online status, ⌘K hint, theme toggle | `TopBar.jsx` | `GET /api/site` (avatar via GitHub, location string) | owned |
| 01 | terminal hero — `~/<handle> on main`, `$ whoami`, `name`/`name_en`, `Backend · AI ~~Fullstack~~`, typed-out `typing_line`, `stack_chips` row | `HomeA.HeroA` | `GET /api/site` (`handle, name, name_en, typing_line, stack_chips`) | owned |
| 02 | contributions heatmap (52 weeks × 7 days) with hover radial-glow + tooltip | `HomeA.ContribGraph` | `GET /api/contrib?weeks=52`; total from `site.commits52w` | derived (GitHub-synced) |
| 03 | `./posts` index — tag pillbar, post rows `#n · date · title — subtitle [tag] · ◷ read`, j/k focus + Enter | `HomeA` post list | `GET /api/posts?tag=&limit=100`, `GET /api/tags` | owned |
| 04 | `~/projects` cards — `name / desc / lang / ★ stars / status` | `HomeA` projects | `GET /api/projects` | owned (curated GitHub mirror) |
| 05 | `/contact` row — email (copy), github (link), 小红书, 抖音 (currently hardcoded literals in `HomeA.jsx:400-426`) | `HomeA` contact row | `GET /api/site` (`email, github`); `apiContacts` exists but **unused on public** | owned (currently part-hardcoded) |
| footer | `© year · hand-coded · no trackers · powered by coffee`, github link, email copy | `App.jsx:195-215` | `site.name_en, handle, github, email`; year/strings hardcoded | owned + hardcoded |
| pet | floating ASCII desktop pet — sprite, speech bubble, profile dialog, settings panel, chat input | `AsciiPet.jsx` | `GET /api/pet/config`, `POST /api/pet/summon/stream` (SSE), `POST /api/pet/forget` | mixed |
| palette | ⌘K command palette merging theme/accent commands + every post by title | `Palette.jsx` | `GET /api/posts` (read-only) | owned |
| konami | hidden GODMODE card on Konami sequence | `Konami.jsx` | none | owned (Easter egg) |

Interactive surfaces on `/`: tag pill click, post-row focus (j/k), post-row click → reader, ⌘K palette, theme toggle (`t`), Konami buffer, pet drag/click/long-press/chat, footer email copy, contact-row copy. `App.jsx` exposes `window.__petScene = () => ({...})` carrying `page_type, active_tag, focused_post_title, visible_posts, home_digest, …` for the pet.

### 1.2 Route `/p/:id` — Reader

`Reader.jsx` swaps in for `HomeA`. Same chrome (TopBar, Palette, Pet, Konami) stays mounted.

| Region | Renders | Backing API | Owned vs derived |
|---|---|---|---|
| reader-progress | scaleX bar tracking scroll % | client-only | n/a |
| reader-toc | back button, "on this page" h2 anchors numbered `01 02 …`, stat block (`read / chars / tag / updated`) | `post.body[]` h2s; `post.read, word_count, tag, date` | owned |
| reader-hero | eyebrow `#n · date · #tag · ◷ read`, h1, serif subtitle (zh: `Noto Serif SC`; en: `Newsreader`) | `GET /api/posts/:id` | owned |
| TL;DR box | optional `tldr` field | `post.tldr` | owned |
| reader-body | typed blocks: `h2/h3/h4/p/code (with language sniff + copy)/hr/quote/ul/ol/table`; inline runs `text/code/b/i/a` | `post.body[]` AST | owned |
| reader-stub fallback | "[ full article draft in progress … ]" + `summary` when body empty | `post.summary` | owned |
| reader-reactions | Like (♡→♥, **localStorage-only today** despite `POST /api/posts/:id/like` existing), copy-link, share | local | derived (broken) |
| reader-author | avatar, `name`, `tagline`, github link, email copy | `GET /api/site` | owned |
| reader-related | up to 3 same-tag posts (excluding current) | filtered `GET /api/posts` | owned |
| reader-navfoot | older / newer by index in posts list | `GET /api/posts` | owned |
| reader-signoff | `— <name>, <date>` + `press esc to go back` | `site.name`, `post.date` | owned |

Interactive: scroll-driven progress, anchor-jump, text selection ≥5 chars triggers pet hint, code copy fires `pet:reader-action`, like, copy-link, share, related-card click, prev/next, esc. Reader fires a hit beacon on every `post.id` change. Reader's `window.__petScene` carries `page_type:'post', read_progress, active_heading, visible_block_type, selection_kind, dwell_seconds, recent_action, post_id, …`.

### 1.3 Top-bar nav anchors

`/`, `/writing`, `/projects`, `/now`, `/contact` smooth-scroll to `#top`, `#writing`, `#projects`, `#now`, `#contact` on home. **The `/now` link points at the contributions section head (`HomeA.jsx:315 id="now"`)** — there is no rendered `/now` body section despite `apiNow` existing server-side. Gap.

---

## 2. Public data contracts

Read paths actually consumed by the public app, grouped by feature. The admin must own every endpoint in this table that touches "owned" data.

### 2.1 Site identity / profile

| Endpoint | Public consumers | Returns / accepts |
|---|---|---|
| `GET /api/site` | `App.jsx`, `HomeA.HeroA`, `HomeA` body, `TopBar`, `Reader`, `Palette` (indirectly) | `{ handle, name, name_en, tagline, github, email, location, typing_line, stack_chips[], commits52w }` |
| `GET /api/profile` | hook exists in `hooks.js`, **no consumer in public components** | `{ name, role, bio, avatar_path, stack_chips, … }` |
| `GET /api/contacts` | hook exists, **no consumer** | visible-only contact rows |

The split between `/api/site` and `/api/profile` is artificial — both project from the singleton `site_meta` row.

### 2.2 Content

| Endpoint | Public consumers |
|---|---|
| `GET /api/posts?tag&limit` | `App.jsx`, `Reader`, `Palette` |
| `GET /api/posts/:id` | `Reader` |
| `POST /api/posts/:id/like` | **defined in `client.js` but not invoked** by Reader; likes are localStorage-only today |
| `GET /api/tags` | `App.jsx` (passes to `HomeA`) |
| `GET /api/projects` | `HomeA` |
| `GET /api/contrib?weeks` | `HomeA` |
| `GET /api/now` | (no public consumer; admin writes only) |

### 2.3 Engagement

| Endpoint | Public consumers |
|---|---|
| `GET /api/posts/:id/comments` | **no public component renders it** — admin moderates a queue with no public surface |
| `POST /api/posts/:id/comments` | **no public component submits it** |
| `POST /api/hit` | every page load (`main.jsx`); Reader on `post.id` change |

### 2.4 Pet

| Endpoint | Public consumer |
|---|---|
| `GET /api/pet/config` | `AsciiPet.jsx:82` (returns `{ enabled, assigned_species }`) |
| `POST /api/pet/summon/stream` | `AsciiPet.jsx:399` (SSE: `meta`/`chunk`/`done`/`fallback`/`rate_limited`/`cache_hit`/`error`) |
| `POST /api/pet/forget` | `AsciiPet.jsx:947` ("forget me" button) |

`pet/summon/stream` payload modes used by `pet/payload.js` + `AsciiPet.jsx`: `greet`, `recommend_next`, `summary_react`, `selection_explain`, `selection_qa`, `free_chat`, `idle_monologue`, `article_finished`, `code_assist`, `pet_care`, plus the backend also accepts `follow_up`, `reading_assist` (12 modes total).

### 2.5 Hardcoded / unmanaged surfaces (PRD must account for these)

- `小红书 xhslink.com/m/4la2YRNQF1u` and `抖音 604691290` literals in `HomeA.jsx:400-426`.
- Footer copy `© 2026 …`, `hand-coded`, `no trackers`, `powered by coffee` literals in `App.jsx:196-199`.
- Accent presets `green / amber / violet` in `utils/accent.js` (oklch literals).
- Pet species catalogue (28 entries with rarity, color, trait, frames, localLines, behavior) in `src/components/pet/species.js`.
- Pet idle/proactive timing constants (`IDLE_MONOLOGUE_MS = 90000`, etc.) in `AsciiPet.jsx`.
- Pet reaction tints / state colors in `AsciiPet.jsx:17-31`.

---

## 3. Visitor experience goals

Reverse-engineered from the components, README, and copy. The admin must protect and serve these — it must never become a generic SaaS dashboard sitting next to a bespoke public site.

1. **Terminal-as-aesthetic** — every page wears a shell motif: `~/<handle> on main`, `$ whoami`, numbered `01 / 02 / 03` section heads, paths `./posts ~/projects /contact`, `&lt;chip ✓&gt;`, monospace default, `&lt;kbd&gt;` shortcut hints.
2. **Reading-first** — Reader is a long content column with sticky TOC, scroll-progress bar, `◷ read`-time, character count, related cards, prev/next. Zero ads, zero modals, zero trackers (footer literally states this).
3. **Hand-coded, dev-oriented voice** — README: "hand-built". Tags: `backend, ai, ml, devtools, infra`. Heading: `Backend · AI ~~Fullstack~~`. Every interaction has a keyboard analogue (`⌘K /`, `j k Enter`, `t`, `esc`).
4. **Live & alive** — contributions heatmap signals the author actually writes code. Hero typing animation makes the page feel like it's booting. Pet sleep/yawn/startled states make it feel inhabited.
5. **Pet companion** — not chrome; a contextual reading buddy that knows `active_tag, focused_post, read_progress, active_heading, visible_block_type, selection_kind, dwell_seconds`, and proactively offers summaries / code explanations.
6. **Deterministic identity per visitor** — IP+UA hash → assigned species across cache wipes. Legendary species fire a one-time celebration. The pet is treated as an identity, not a UI element.
7. **Bilingual reading** — `lang === 'zh'` switches body to `Noto Serif SC`; English stays `Newsreader`. Pet `localLines` are intentionally Chinese for several species.
8. **Discoverable but minimal** — ⌘K palette merges commands and posts. Konami unlocks a hidden GODMODE card. Easter eggs reward exploration without clutter.
9. **Author-as-author signal** — every post ends with avatar + name + tagline + github + email + `— <name>, <date>`. Personal-blog feel, not a publication feel.
10. **Self-owned, portable** — README markets it as single-tenant publishing infra with one-click export. Frontend has no social SDKs.

The admin must let the owner *protect* every one of these properties. Sloppy admin UX → sloppy public copy → broken voice. The admin is the studio behind the stage.

---

## 4. Admin capabilities reverse-engineered from §1–3

We rebuild the admin module list **bottom-up** from public regions and visitor-derived state, not from DB tables. Each capability below names the public surface it serves.

### 4.1 Capabilities serving owned content

| # | Capability | Serves frontend region | Today |
|---|---|---|---|
| C1 | Edit a post's content + metadata via a markdown editor with **GUI** for `status / scheduled_at / featured / private / comments_enabled / tag / lang`, live preview that matches the public Reader, media insert, autosave/draft recovery | `/p/:id` reader, `/` post list | exists as raw frontmatter text (`PostEditor.jsx`); no GUI, no media insert, no autosave |
| C2 | Bulk-import / bulk-overwrite posts via `.md` upload with reportable success/failure | `/` post list growth | endpoint `POST /api/admin/posts/upload` exists but **no UI** |
| C3 | Curate the tag pillbar — order, color, slug; refuse delete on referenced tags | `/` tag pillbar | done (`Tags.jsx`) |
| C4 | Edit projects card content; pull from GitHub on demand; reorder | `/` projects grid | inline-edit table done (`Projects.jsx`); **no GitHub repo autofill despite the integration syncing repos** |
| C5 | Edit / append / archive `now` entries with markdown preview matching public render | future `/now` panel + reader signal | composer + timeline done (`Now.jsx`); **no preview**, and **no public consumer for `/api/now` exists** |
| C6 | Manage media library with **usage backreference** (which posts use this image, is this the avatar) | `/p/:id` body images, profile avatar, future media-in-post insert | grid + upload + alt + delete done; **no usage backreference**; deleting an in-post-referenced image silently orphans it |
| C7 | Edit the singleton site identity — `handle, name, name_en, tagline, role, bio, location, pronouns, github, email, avatar, typing_line, stack_chips, footer_note, default_theme, launched_at` — as **one workflow** ("站点身份"), not split in two pages | every public region | split awkwardly between `/admin/profile` and `/admin/site` (same DB row, fake division) |
| C8 | Manage public contacts list with **social-icon presets and href validation**; render preview chip | `/contact` row | inline-edit table exists; **`HomeA.jsx` hardcodes 小红书 + 抖音 because the contacts list isn't wired into the public render** |
| C9 | Edit theme — accent + accent2 + violet + danger — via a **color picker with live preview**, not raw oklch strings | TopBar + body + pet color-mix | currently raw text inputs (`Site.jsx`) |

### 4.2 Capabilities serving visitor-derived state

| # | Capability | Serves | Today |
|---|---|---|---|
| O1 | Comment moderation queue with status tabs, **per-post filter, bulk approve/reject, public-link-back, IP/email-hash spam hints** | `Reader` future public comments + admin oversight | tabs + inline reply + optimistic moderation done; **no per-post filter, no bulk** |
| O2 | Pet conversation log per visitor with **visitor-profile inspector** (`style_summary, memory_summary, interest_tags, recent_post_ids, interaction_count, proactive_muted_until`) and "delete & forget" | pet companion behaviour | conversation list + transcript + delete done; **profile fields not surfaced** |
| O3 | Pet usage with **per-mode / per-provider / fallback-rate charts** + cost extrapolation | pet integrations cost monitoring | flat day×mode×source table only |
| O4 | Site analytics with **custom date range, compare-to-previous, drill-down, CSV export, per-post traffic page** | hit beacon → editorial intuition | 7/30/90 chips + top-N done; nothing else |
| O5 | Likes per post — **real server-truth display** (today the public Reader writes to localStorage only, so admin sees zero). Either wire the public POST or delete the table; PRD requires wiring it. | Reader reactions row | half-built |
| O6 | Recent **activity feed** on dashboard + a full activity log page (every admin write writes to `event_log`; backend route exists, **no UI** today) | post-mortem / oh-no recovery | gap |

### 4.3 Capabilities serving system state

| # | Capability | Today |
|---|---|---|
| S1 | Login that **handles 2FA challenge** (today's UI does not — accounts with 2FA enabled cannot log in) | broken |
| S2 | **Refresh-token rotation** wired in `AuthContext` so the admin doesn't silently drop you to login every `access_token_ttl` | broken (no call) |
| S3 | Account: 2FA setup/disable/regen, password change, magic-link enable, **email change** (backend gap too) | partial; email change missing |
| S4 | API tokens — list, create-once-secret, revoke, **per-token last-used + usage history** | half (no usage history) |
| S5 | Integrations — GitHub + 5 LLM providers — with **"test connection without saving"**, smoke-test on save (already done), **provider priority ordering UI** (today set via comma string in Pet → Behavior) | partial |
| S6 | Pet templates editable for **all 12 modes** (today only 5 of 12 are exposed) | partial |
| S7 | Pet species catalogue editable from the admin (rarity, color, trait, frames, behavior, localLines) — **today hardcoded in `species.js`** | gap |
| S8 | Danger ops: export with scope picker, import with diff preview, delete-site with countdown + cancel | exists but always-everything |

### 4.4 Capabilities cross-cutting every workflow

- Global **command palette** (⌘K) and global **keyboard shortcuts** (j/k, g d / g p / g c, `/` to search) — admin currently has zero of these.
- Filters & pagination in **URL query string** so links are bookmarkable / shareable. Today only Pet uses `?tab=`.
- Unified **confirm + toast** patterns. Today admin uses native `confirm()` / `alert()` in 6 places, custom `ConfirmModal` in DangerZone, custom `SecretModal` in ApiTokens, inline error banners in Posts/Pet, and toasts in Profile/Site/Media — five different mental models.
- Every admin row that points at a public-visible object needs a "view on public site" link.
- Empty states must include onboarding hints linking to "create your first X" actions.

---

## 5. Information architecture

### 5.1 Today's IA — flat, ungrouped

`Layout.jsx` ships **13 flat sidebar items, no group headings**, in order:

`概览 · 数据分析 · 文章 · 媒体库 · 评论 · 标签 · 站点 · 作者资料 · 联系方式 · 项目 · 近况 · 宠物助手 · 设置`

Settings buries 4 sub-tabs (集成 / API 令牌 / 账号 / 危险操作); Pet buries 5 (行为 / 人格 / 模板 / 对话 / 用量). Both are inconsistent — Pet syncs `?tab=`, Settings does not. There's no breadcrumb beyond `~ / admin`.

### 5.2 Proposed IA — six groups, workflow-shaped

Sidebar regrouped by *what the owner is trying to do*. Numbered headings echo the public site's `01/02/03` motif. Order chosen so the most frequent inbox/dashboard work sits at top, content authoring next, observation third, brand fourth, pet fifth, system last.

```
01 · 运营中枢
   仪表盘             — KPIs + 最近活动 feed (最近 20 条 event_log)
   收件箱             — 待审评论 + 最近宠物对话 + magic-link/login 异常 (统一收件流)

02 · 内容
   文章               — 列表 + 编辑器 (GUI 字段 + media insert + autosave)
   标签               — 现有
   媒体               — 现有 + 反向引用
   近况               — 现有 + 预览
   项目               — 现有 + GitHub 一键导入

03 · 观察
   数据分析           — 现有 + 自定义时段 + 导出 + per-post 详情
   宠物对话           — 现有 + 访客档案
   宠物用量           — 现有 + 图表

04 · 首页与品牌
   站点身份           — 合并 Profile + Site (除主题)；唯一编辑 site_meta
   联系方式           — 现有 + 社交图标预设 + 校验；并接入公开页面 (替代 HomeA 硬编码)
   主题               — accent / accent2 / violet / danger 颜色拾取器 + 实时预览

05 · 宠物配置
   行为               — 现有；切换 tab 前提示未保存
   人格               — 现有 (per species localLines)
   模板               — 12 个 mode 全开放
   物种目录           — 新页：rarity/color/trait/frames/behavior/localLines

06 · 系统
   集成               — 现有 + test-without-save + provider 优先级排序
   API 令牌           — 现有 + 使用历史
   账号               — 现有 + 邮箱修改
   活动日志           — 新页 (event_log 完整时间线 + 类型筛选)
   危险操作           — 现有 + 导出范围选择
```

13 → 21 items, but distributed across 6 named groups. Two new modules (收件箱、活动日志、物种目录) plus one merge (Profile + Site → 站点身份) plus one split (Site → 站点身份 / 主题).

### 5.3 Per-module rationale

- **运营中枢** exists because the owner's most common visit is "what needs my attention right now?" Not "let me browse a table."
- **内容** keeps "things I write" together. Posts is the centerpiece; tags/media/now/projects are the ecosystem.
- **观察** isolates read-only visitor signals. Operationally distinct from authoring.
- **首页与品牌** owns everything visible above the fold on `/`. Site identity is one workflow, not two.
- **宠物配置** is large enough to warrant its own group — pet is a first-class brand surface, not a side feature.
- **系统** is everything an owner shouldn't have to think about most days.

### 5.4 URL conventions

- `/admin/inbox`, `/admin/posts`, `/admin/posts/:id` (editor), `/admin/comments`, `/admin/pet/conversations/:visitor_hash`, etc.
- All filters + pagination in query string: `?status=pending&post=foo&page=2`.
- Pet sub-pages flatten into top-level URLs (`/admin/pet/behavior`, `/admin/pet/personas`, `/admin/pet/templates`, `/admin/pet/species`) — matching the IA above.

---

## 6. Visual & interaction principles

### 6.1 Visual language — must mirror the public site

The public site's design language (extracted from `HomeA`, `Reader`, `Palette`, `TopBar`, `AsciiPet`) is the *constraint*, not a starting point we get to tune. The admin must inherit:

- **Monospace default** — `'JetBrains Mono', ui-monospace, Menlo, monospace`. Already true today.
- **OKLCH accent system** — `--accent / --accent-glow / --accent-2 / --violet / --danger`. Use `color-mix(in oklab, …)` for tints. Already true today.
- **Numbered section heads** — `<span class="n">01 /</span> posts <span class="count">42 entries</span>`. Today's admin doesn't have this; PRD requires adopting it for major page heads.
- **Uppercase 9–10px tracked labels** for column headers, eyebrows, kicker rows: `letterSpacing: 0.08em–0.12em, textTransform: uppercase, color: var(--fg-4)`. Already partially used.
- **Dense list rows** with `.focus` highlight — the public post list pattern. Admin tables should adopt the same row-as-record feel.
- **Pill / chip components** matching public ones (`borderRadius: 999/3, padding: 4-7px, fontSize: 10-11px, lowercase`).
- **`<kbd>` shortcut hints** wherever a shortcut is offered. Public uses them; admin currently doesn't.
- **Terminal copy** in section heads and empty states: `./posts`, `~/projects`, `$ no drafts yet — type \`g d\` to create one`. Loading state: `<div class="prompt">loading…</div>` not a spinner.
- **Bilingual-aware** strings — Chinese is the primary admin locale today, but typography (Noto Serif SC for serif content, JetBrains Mono otherwise) must remain consistent.
- **Code blocks** in any admin preview / docstring panel use the macOS-window styling (three traffic-light dots + language tag + copy chip) from Reader.
- **Pet presence in admin** — `window.__pet.trigger('building'/'happy'/'error', duration)` is already a public API. The admin can adopt it for save / build / error feedback so the pet becomes the unified status surface.

### 6.2 Interaction principles

- **Keyboard-first**. Every page must support: `j/k` row focus, `Enter` open, `e` edit, `?` keyboard-help dialog, `g d/g p/g c/g m/...` jump to module, `⌘K /` palette, `t` theme toggle (already public). No important action is mouse-only.
- **One confirm pattern**. Replace every `confirm()` / `alert()` with a single `ConfirmModal` component reused everywhere; replace inconsistent error feedback with one toast pattern.
- **Optimistic mutations** with rollback on error, where feedback latency matters (status flip, reorder, toggle visible). Already partially true.
- **URL = state**. Refreshing or sharing a URL must restore filters, pagination, tab.
- **Empty states do work**. Every empty state must include 1) what this is, 2) the keystroke or button to create one, 3) a link to the public surface this controls.
- **Saving discipline**. No tab switch silently discards unsaved data. Pet's "保存 saves whichever tab is open" footgun must be fixed.
- **No surprise destruction**. Deleting media that's referenced by a post must warn first; deleting a tag with referenced posts already does (keep). Deleting a profile avatar source must warn (already added in last loop).

### 6.3 What we are *not* building

- No KPI hero banners, no "Welcome back, $name" cards, no marketing-style dashboards.
- No drag-and-drop kanban, no chart wonderland, no GA / Mixpanel-style breakdowns beyond what `O4` already specifies.
- No third-party UI kit (Material, Ant, Chakra, shadcn). Hand-built primitives matching the public site.
- No theme switcher in the admin chrome — admin follows `default_theme` plus a developer-only override.
- No multi-tenant abstractions. Single owner, period.

---

## 7. Current-state gap matrix

Source: cross-reading the audit report against §4. "Existing" = code shipped and at least functionally complete; "half-built" = exists but missing a key affordance; "gap" = not present.

| Capability | Existing | Half-built | Gap | Severity |
|---|:--:|:--:|:--:|---|
| C1 Posts editor with GUI fields, media insert, autosave | | ✓ (raw frontmatter only) | | high |
| C2 Bulk markdown upload UI | | | ✓ (backend ready) | medium |
| C3 Tags list + reorder + protected delete | ✓ | | | — |
| C4 Projects + GitHub repo autofill | | ✓ (no autofill) | | medium |
| C5 Now composer + markdown preview + public render | | ✓ (no preview, no public surface) | | medium |
| C6 Media + usage backreference | | ✓ (only avatar lookup) | | medium |
| C7 Site identity merged workflow | | ✓ (split across two pages) | | high |
| C8 Contacts wired into public + presets + validation | | ✓ (wiring), | (presets, validation) | high |
| C9 Theme color picker | | ✓ (raw oklch strings) | | medium |
| O1 Comments moderation: per-post filter, bulk, link-back | | ✓ | | medium |
| O2 Pet visitor profile inspector | | | ✓ (data exists, not surfaced) | medium |
| O3 Pet usage charts + cost | | | ✓ (flat table only) | low |
| O4 Analytics: custom range, drilldown, export | | ✓ | | medium |
| O5 Likes wired server-side + admin display | | ✓ (broken in public Reader) | | high (data integrity) |
| O6 Activity feed + full log page | | | ✓ (backend ready, no UI) | high |
| S1 Login 2FA challenge handling | | | ✓ (broken) | **critical** |
| S2 Refresh-token rotation in AuthContext | | | ✓ (broken) | **critical** |
| S3 Email change (backend + UI) | | | ✓ | medium |
| S4 API token usage history | | ✓ | | low |
| S5 Integrations: test-without-save, provider priority UI | | ✓ | | medium |
| S6 Pet templates: 12/12 modes | | ✓ (5/12) | | high |
| S7 Pet species catalogue admin | | | ✓ (hardcoded) | medium |
| S8 Danger ops scope/diff | | ✓ | | low |
| Cross-cut: command palette + keyboard shortcuts | | | ✓ | high |
| Cross-cut: URL filters/pagination | | ✓ (Pet only) | | medium |
| Cross-cut: unified ConfirmModal + Toast | | ✓ (5 patterns) | | medium |
| Cross-cut: section-head + kbd visual language | | ✓ | | medium |
| Cross-cut: empty-state onboarding | | | ✓ | low |
| Cross-cut: "view on public site" links | | | ✓ | low |
| IA: re-grouped sidebar | | | ✓ | high |
| IA: 收件箱 page | | | ✓ | medium |
| Hardcoded: HomeA contacts row reads from API | | | ✓ | high |
| Hardcoded: /now public render or unlink | | | ✓ | medium |
| Hardcoded: footer copy editable or auto-derived | | | ✓ | low |

The implementation plan picks tasks off this matrix. Critical items (S1, S2) ship first.

---

## 8. Out of scope

- Migrating the public site away from Vite/React.
- Backend infrastructure changes (Postgres → anything else; Redis → anything else; auth provider swap).
- Multi-author / multi-tenant.
- Public-facing comment UI design (only the admin moderation surface; the public render is a separate decision tracked elsewhere).
- A third-party admin framework. No `react-admin`, no `refine`, no `payload`. Hand-built only.
- Pet model retraining or LLM finetune.

---

## 9. Success criteria

1. Every long-term-maintained piece of public copy / data has an owner-editable surface in admin (no more `HomeA.jsx` hardcoded contact links, no more raw `oklch(...)` strings, no more "split across two pages because that's the schema").
2. The owner can ship a new post end-to-end from a single admin screen — content + status + schedule + tag + image + preview — without typing YAML by hand.
3. Sidebar IA matches §5.2 with breadcrumbs and keyboard shortcuts.
4. Login works with 2FA enabled. Sessions stay alive past the access-token TTL via refresh rotation.
5. The admin's visual language is indistinguishable from the public site's vocabulary (font, spacing, accent system, section-head numbering, `<kbd>` chips, terminal copy).
6. Every task in the task-index has a unique git commit; every "completed" entry records a commit hash, test result, and Playwright verification.
7. No new screen looks like a database table editor; every screen is shaped around a workflow named in §4.

---

## 10. Implementation hand-off

The implementation plan with per-task scope, files, tests, Playwright paths, and commit messages is in:

`docs/superpowers/plans/2026-05-05-admin-frontend-driven-task-index.md`

Round 1 of the rebuild ships only this PRD and that plan (Task 0).
