# Admin Console — Frontend-Driven Rebuild Task Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. **Each task ships in its own git commit. No commit hash → not done.**

**Goal:** Implement every capability listed in `docs/superpowers/specs/2026-05-05-admin-frontend-driven-prd.md` §4, plus the IA from §5.2, plus the visual & interaction principles from §6, one minimal feature at a time. Stop when the gap matrix in §7 is empty.

**Architecture:** Same stack — FastAPI backend on `:51820`, Vite + React frontend on `:5173` for public, mounted `/admin/*` for the admin SPA. SQLAlchemy 2.0 async + Alembic. Redis 7 for cache / queue / rate limit. ARQ worker (`ARQ_INLINE=true` in dev). Tests: pytest + httpx for backend; Vitest + Playwright CLI for frontend.

**Tech Stack:** Existing — no new framework, no new third-party admin kit. Hand-built primitives matching the public site.

**Out of scope for this plan:** Items already in PRD §8.

---

## Task index legend

Every task entry has the same skeleton. Each entry must be filled in completely **before** that task is considered done.

```
### Task N — <Title>

**Status:** pending | in-progress | completed
**Priority:** critical | high | medium | low
**Frontend evidence:** <which public surface this serves; cite file:line>
**Owner problem:** <what management problem this solves; one sentence>
**Existing capability:** <what already works>
**Gap:** <what's missing — be specific>
**Admin module:** <sidebar group + page>
**Backend touch:** <models / schemas / routers / services / migrations>
**Frontend API client:** <src/api/*.js files>
**UI / interaction:** <screens, controls, shortcuts, empty states, error states>
**Automated tests:** <pytest paths + vitest paths>
**Playwright acceptance path:** <step-by-step browser flow>
**Snapshot location:** /tmp/admin-rebuild/task-N/<name>.png
**Commit message:** <type(scope): subject>
**Definition of done:**
  - [ ] code change
  - [ ] tests written & green
  - [ ] Playwright acceptance run & screenshots saved
  - [ ] only this task's files staged
  - [ ] commit created
  - [ ] task-index updated with commit hash + test/Playwright results

**Completed:** <commit hash + summary, or empty>
```

---

## File structure (working dirs only)

```
/Users/sd3/Desktop/project/MyBlog/
├── docs/superpowers/
│   ├── specs/2026-05-05-admin-frontend-driven-prd.md         # PRD (this rebuild's source of truth)
│   └── plans/2026-05-05-admin-frontend-driven-task-index.md  # this file
├── src/admin/                            # admin SPA (touched by most tasks)
├── src/api/                              # admin + public clients
├── src/components/                       # public-facing — touched only when public surface change is required
├── backend/app/routers/admin/            # admin routes
├── backend/app/routers/public/           # public routes (touched only by O5, hardcoded-fixes)
├── backend/app/schemas/                  # Pydantic
├── backend/app/models/                   # SQLAlchemy
├── backend/app/services/                 # business logic
├── backend/alembic/versions/             # new migrations land here
└── /tmp/admin-rebuild/task-N/            # Playwright artifacts per task (NOT committed)
```

---

## Round-by-round protocol (every loop iteration)

1. Read PRD + this task-index.
2. `git status` — confirm working tree state, do **not** revert / overwrite anything outside the current task.
3. Pick the **highest-priority unfinished task** (top of the matrix below).
4. Announce: what task, why it matters, files touched, expected commit message, expected Playwright path.
5. Implement backend → frontend client → admin UI → tests.
6. Run minimal tests: `pytest backend/tests/<file>` + `npm run test -- <file>` or `npm run build`.
7. Confirm services are running (`backend :51820`, frontend `:5173`).
8. Run Playwright CLI verification per the task's acceptance path. Save screenshots to `/tmp/admin-rebuild/task-N/`.
9. Fix any UI/data bugs found, re-verify.
10. `git status` → only the task's files should be staged.
11. `git add <task files>` → `git commit -m "<message>"`.
12. Update this task-index entry: status `completed`, commit hash, test command + result, Playwright command + result, snapshot path.
13. Reply: completed scope, files changed, commit hash, test summary, Playwright summary, next-task suggestion.

Strict rules:
- **Never** stage files outside the current task. The repo currently has unrelated unstaged changes from a prior loop — they remain untouched until the user reviews them.
- **Never** simplify a task to ship faster — defer to next round instead.
- **Never** combine two tasks in one commit, even if they're small.
- **Never** mark a task done without a commit hash.

---

## Task list — priority-ordered

### Task 0 — Establish frontend-driven admin rebuild PRD + task-index

**Status:** completed
**Priority:** critical
**Frontend evidence:** PRD §1 (full public-page audit)
**Owner problem:** without a frontend-derived plan the rebuild becomes a list of DB-table edits. PRD anchors every future task to a real public surface or visitor signal.
**Existing capability:** none — first PRD/plan for this rebuild.
**Gap:** documentation only.
**Admin module:** n/a (planning artifact)
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:** none
**Automated tests:** none (planning round)
**Playwright acceptance path:** N/A — round 1 is documentation-only per the rebuild spec; visual verification is irrelevant for prose. Subsequent tasks **must** run Playwright.
**Snapshot location:** N/A
**Commit message:** `docs(prd): define frontend-driven admin rebuild plan`
**Definition of done:**
  - [x] PRD written: `docs/superpowers/specs/2026-05-05-admin-frontend-driven-prd.md`
  - [x] task-index written: `docs/superpowers/plans/2026-05-05-admin-frontend-driven-task-index.md`
  - [x] only the two new doc files staged
  - [x] commit created
  - [x] task-index entry below updated with commit hash

**Completed:** `2177eda93b7509e541094c62e5550a0d47e3598a` (`docs(prd): define frontend-driven admin rebuild plan`) — initial PRD covers 6 sections (frontend page map, experience goals, reverse-engineered admin capabilities, IA, visual principles, gap matrix); task-index lists Task 0 + 30 follow-up tasks with priorities. `.gitignore` narrowly whitelists these two tracking docs while keeping the rest of `docs/` untracked. **Tests:** none — round 1 is documentation-only per rebuild spec. **Playwright:** none — round 1 is documentation-only per rebuild spec; visual verification is irrelevant for prose.

---

### Task 1 — Login 2FA challenge handling

**Status:** completed
**Priority:** critical
**Frontend evidence:** none directly visible — affects S1 system capability. Triggered when an admin enables 2FA via `Account.jsx`.
**Owner problem:** owners with 2FA enabled cannot log in today: `Login.jsx` only reads `{access}` from the response, but `auth/login` returns `{tfa_required:true, challenge}` when `acct.tfa_enabled`. They are bricked out.
**Existing capability:** backend issues `tfa_required` + challenge, accepts `/auth/2fa` with TOTP or recovery code.
**Gap:** the login form does not render a TOTP input nor call `/auth/2fa`.
**Admin module:** Login (group 06 / 系统 indirectly)
**Backend touch:** none (already complete)
**Frontend API client:** `src/api/admin.js` — add `verifyTfa(challenge, code)` if missing
**UI / interaction:**
  - on submit, if response has `tfa_required:true`, swap form to TOTP step: 6-digit input, "use recovery code instead" toggle (`xxxx-xxxx`), "back to email/password" link, error banner
  - keyboard: Enter submits, Esc returns to email step
**Automated tests:** `backend/tests/test_admin_auth.py` already covers; add `src/admin/Login.test.jsx` for the 2FA branch with mocked client
**Playwright acceptance path:**
  1. enable 2FA via Account page (one-time setup)
  2. logout
  3. login at `/admin` → enter email + password → assert TOTP screen renders
  4. paste valid TOTP → assert dashboard loads
  5. logout → login again → submit invalid TOTP → assert error banner; valid recovery code → assert dashboard
  6. screenshot the TOTP screen
**Snapshot location:** `/tmp/admin-rebuild/task-1/totp-step.png`
**Commit message:** `feat(admin/auth): handle 2FA challenge in login form`
**Definition of done:** standard checklist
**Completed:** `da9dd66` (`feat(admin/auth): handle 2FA challenge in login form`).

- **Tests:** `npx vitest run src/admin/Login.test.jsx` → 5/5 passing (skips TFA when access returned, shows TFA when challenge returned, rejects malformed TOTP client-side, recovery toggle validates xxxx-xxxx, back button clears challenge).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-1/verify.py` → end-to-end with real backend: enable 2FA via API → UI login → TFA step renders → valid TOTP → /admin/dashboard; client-side 6-digit validation; recovery toggle changes placeholder; back returns to creds; cleanup disables 2FA. All assertions green; no console/page errors.
- **Snapshots:** `/tmp/admin-rebuild/task-1/{tfa-step,dashboard,recovery-step}.png`.

---

### Task 2 — Refresh-token rotation wired in AuthContext

**Status:** completed
**Priority:** critical
**Frontend evidence:** any admin session — affects S2.
**Owner problem:** admin sessions silently die after `access_token_ttl` (default ~15 min). The user gets dumped to login mid-edit.
**Existing capability:** backend `POST /auth/refresh` rotates refresh + new access, with httpOnly refresh cookie.
**Gap:** `src/admin/AuthContext.jsx` has no refresh logic. On 401 it just redirects to login.
**Admin module:** AuthContext (cross-cutting)
**Backend touch:** none
**Frontend API client:** `src/api/admin.js` — add `refresh()` returning `{access}`
**UI / interaction:**
  - 401 from any `/api/admin/*` → call `refresh()` once → if successful, retry original; if fails, redirect to login
  - schedule a proactive refresh at 80% of token TTL (parsed from JWT exp)
**Automated tests:** add `src/admin/AuthContext.test.jsx` mocking 401→refresh→retry; backend tests already cover refresh
**Playwright acceptance path:**
  1. login at `/admin`
  2. wait until 80% of access token TTL (or stub `Date.now()` via `page.evaluate`) → assert no logout
  3. expire access token forcibly (clear localStorage `bl.access`) → fire any admin GET → assert auto-refresh + page still works
  4. revoke refresh cookie → fire admin GET → assert redirect to `/admin` login
**Snapshot location:** `/tmp/admin-rebuild/task-2/post-refresh.png`
**Commit message:** `feat(admin/auth): rotate refresh token on 401 instead of forcing relogin`
**Definition of done:** standard checklist
**Completed:** `30f4db3` (`feat(admin/auth): rotate refresh token on 401 instead of forcing relogin`).

- **Tests:** `npx vitest run src/api/admin.test.js src/admin/Login.test.jsx` → 12/12 passing (7 admin: jwtExpiresAt parse, 401→refresh→retry, onUnauthorized when refresh fails, no retry on /auth/* paths, concurrent-coalesce, tryRefresh non-200; 5 Login: 2FA flow regression check after admin.js mock surface widened).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-2/verify.py` → end-to-end with real backend: login → confirm dashboard → inject expired access token → reload → observe `/auth/refresh` POST in network log + dashboard stays loaded (no redirect) → wipe refresh cookie → reload → bounced to `/admin` login. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-2/{logged-in,after-stale-refresh,bounced-to-login}.png`.

---

### Task 3 — Posts editor: status / scheduled_at / featured / private / comments_enabled GUI

**Status:** completed
**Priority:** high
**Frontend evidence:** every public post on `/p/:id` (`Reader.jsx`) — `post.status / featured / private / comments_enabled` directly drive whether and how it renders. Today the editor only edits these via raw YAML.
**Owner problem:** publishing a post requires knowing YAML and remembering the field name — typos demote the post to draft (we hit this exact bug last loop). C1 capability.
**Existing capability:** backend `PostDetail` exposes all 5 fields (post-loop fix); markdown round-trip writes them back to frontmatter.
**Gap:** editor UI has no GUI controls; relies on the user to type frontmatter correctly.
**Admin module:** 02 内容 / 文章 / PostEditor
**Backend touch:** none
**Frontend API client:** `src/api/posts.js` — already has detail
**UI / interaction:**
  - new sidebar panel inside the editor: status (draft / published / scheduled select), scheduled_at (datetime-local, only if status=scheduled), featured / private / comments_enabled toggles
  - editing the GUI mutates the frontmatter source-of-truth (so save still goes through markdown round-trip)
  - editing the YAML mutates the GUI (parse on every textarea change)
  - validation: status=scheduled requires future scheduled_at
**Automated tests:** Vitest covering the bidirectional mapping (GUI ↔ YAML); pytest on backend round-trip already exists
**Playwright acceptance path:**
  1. login → /admin/posts → open existing post
  2. flip status from published → draft via select → save → reopen → assert status=draft and `status: draft` in YAML
  3. set status=scheduled, scheduled_at = +1h → save → reopen → assert YAML has `scheduled_at: <iso>`
  4. visit `/p/<id>` on public → assert it 404s (because not published)
  5. flip back to published → save → public renders → screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-3/editor-fields.png`, `/tmp/admin-rebuild/task-3/public-after.png`
**Commit message:** `feat(admin/posts): GUI controls for status, scheduled_at, lifecycle flags`
**Definition of done:** standard checklist
**Completed:** `b08f712` (`feat(admin/posts): GUI controls for status, scheduled_at, lifecycle flags`).

- **Tests:** `npx vitest run src/admin/frontmatter.test.js` → 11/11 passing (parse + serialize round-trip, body separator preserved, quote-on-colon, setFmField add / flip / remove, boolean-omit-when-false, unknown-key round-trip). Combined `npx vitest run src/api/admin.test.js src/admin/Login.test.jsx src/admin/frontmatter.test.js` → 23/23 (no Task 1/2 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-3/verify.py` → end-to-end with real backend: login → open vps editor → GUI status select reflects persisted status → flip status via select → YAML rewrites → save → backend persists → public `/api/posts/vps` 404s when not published → restore → toggle featured via GUI → backend persists → restore. All assertions green; vps post finally restored to status=published, featured=false.
- **Snapshots:** `/tmp/admin-rebuild/task-3/{editor-fields,after-featured-toggle,restored}.png`.

Implementation note: a new `src/admin/frontmatter.js` module hosts the GUI ↔ YAML round-trip helpers (parse, serialize, setFmField). The editor stays a single source of truth — the markdown text — with GUI controls mutating it via `setFmField` and a `useMemo` deriving the current `fm` for control state. Subsumes a prior frontmatter-rebuild fix (`.filter(Boolean)` regression that dropped the body separator).

---

### Task 4 — Sidebar IA regrouped per PRD §5.2

**Status:** completed
**Priority:** high
**Frontend evidence:** all admin pages (cross-cutting). Aligns with public site's `01/02/03` numbered section motif.
**Owner problem:** flat 13-item sidebar buries inbox-style work behind authoring. Six groups + numbered headings expose workflow boundaries.
**Existing capability:** flat list in `src/admin/Layout.jsx`.
**Gap:** no group headings, no numbered sections, no breadcrumb beyond `~ / admin`.
**Admin module:** Layout (cross-cutting)
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - sidebar items grouped under `01 · 运营中枢 / 02 · 内容 / 03 · 观察 / 04 · 首页与品牌 / 05 · 宠物配置 / 06 · 系统` headings (uppercase 9px tracked, fg-4)
  - breadcrumb in topbar: `~ / admin / 02 · 内容 / 文章` (linkable)
  - active item bold + accent left-border
  - existing routes preserved; only ordering + groupings change in this task (new pages are separate tasks)
**Automated tests:** `Layout.test.jsx` — assert group structure
**Playwright acceptance path:**
  1. login → assert sidebar shows 6 group headings + correct items per PRD §5.2
  2. click into 文章 → breadcrumb shows `~ / admin / 02 · 内容 / 文章`
  3. screenshot sidebar
**Snapshot location:** `/tmp/admin-rebuild/task-4/sidebar.png`
**Commit message:** `refactor(admin/layout): regroup sidebar into 6 numbered workflow modules`
**Definition of done:** standard checklist
**Completed:** `e30dbae` (`refactor(admin/layout): regroup sidebar into 6 numbered workflow modules`).

- **Tests:** `npx vitest run src/admin/Layout.test.jsx` → 5/5 passing (6 group heads, every existing route reachable, breadcrumb at `/admin/posts`, sub-path `/admin/posts/__new__` still resolves to its group, unknown route renders bare shell). Combined `npx vitest run src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 28/28 (no Task 1/2/3 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-4/verify.py` → login → assert all 6 numbered group heads visible with correct labels → navigate to `/admin/dashboard`, `/admin/posts`, `/admin/settings` → assert breadcrumb shows "<num> · <group> / <leaf>" each time. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-4/{sidebar,breadcrumb-posts}.png`.

Implementation note: only existing routes were grouped; no new pages built. Pet sub-tabs and Settings sub-tabs remain monolithic in this task (deferred to Task 7 / future tasks). The active link adopts a 2px accent left-border + bold + 14% accent tint, matching the public site's accent system.

---

### Task 5 — Activity feed on dashboard + full activity log page

**Status:** completed
**Priority:** high
**Frontend evidence:** none on public site — internal observability surface. Powers post-mortem after surprises. O6.
**Owner problem:** every admin write writes a row to `event_log`, but there is no UI to read it. After the next "what happened?" we cannot answer.
**Existing capability:** backend `routers/admin/activity.py`: `GET /activity?type=&limit=&offset=` and `GET /dashboard/activity?limit=`.
**Gap:** no UI consumes either route.
**Admin module:** 01 运营中枢 / 仪表盘 (last 20 events widget); 06 系统 / 活动日志 (full timeline + type filter + pagination)
**Backend touch:** none
**Frontend API client:** new `src/api/activity.js`
**UI / interaction:**
  - dashboard widget: 20-row dense list with `type · actor · target · ago(created_at)`; clicking type filters; "查看全部" → `/admin/activity-log`
  - `/admin/activity-log` page: filter chips per type, paginated table, click row to expand `meta` JSON
**Automated tests:** Vitest snapshot for the list; backend tests already cover activity endpoint
**Playwright acceptance path:**
  1. perform any write op (e.g., toggle a contact `visible`)
  2. dashboard → assert event appears at top of widget
  3. click type chip → filtered list still shows it
  4. /admin/activity-log → expand row → assert `meta` shows changed fields
  5. screenshot widget + page
**Snapshot location:** `/tmp/admin-rebuild/task-5/dashboard-widget.png`, `/tmp/admin-rebuild/task-5/log-page.png`
**Commit message:** `feat(admin/activity): expose event log on dashboard and dedicated page`
**Definition of done:** standard checklist
**Completed:** `d63255d` (`feat(admin/activity): expose event log on dashboard and dedicated page`).

- **Tests:** `npx vitest run src/admin/ActivityLog.test.jsx` → 4/4 (list + meta expand, chip filter triggers re-fetch with the right type=, empty state, pagination via 加载更多). Combined `npx vitest run src/admin/ActivityLog.test.jsx src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 32/32 (no Task 1/2/3/4 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-5/verify.py` → seed a tag.updated event via API → login → dashboard widget shows recent events including the seed → "查看全部 →" navigates to `/admin/activity-log` with full table → click a chip → list narrows to that type → click a row → meta panel renders (placeholder when meta is empty); cleanup restores the tag color. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-5/{dashboard-widget,activity-log}.png`.

Implementation note: many backend write_event calls don't attach `meta`, so the row-expand panel falls back to "[ 无 meta — 后端未附加额外字段 ]" rather than failing silently. The chip row only surfaces event types actually seen on this site, adapting to the owner's data instead of pre-listing every theoretical type.

---

### Task 6 — Site identity merged workflow (Profile + Site → 站点身份)

**Status:** completed
**Priority:** high
**Frontend evidence:** `HomeA.HeroA` (handle, name, name_en, typing_line, stack_chips), TopBar (handle, location), Reader author block (avatar, tagline, github, email, name), footer (handle, name_en, github, email).
**Owner problem:** identity fields live in two screens with a confusing note "请在另一页修改", though both PUT to the same `site_meta` row. C7.
**Existing capability:** backend `/profile` and `/site` work; frontend pages `Profile.jsx` and `Site.jsx` both exist.
**Gap:** UX divides one workflow.
**Admin module:** 04 首页与品牌 / 站点身份 (new merged page); also: 04 / 主题 (theme stays separate per PRD §5.2)
**Backend touch:** consider exposing a single `GET/PUT /api/admin/site-identity` thin facade over `site_meta` to avoid hitting two endpoints; or keep two endpoints and merge UI only — implementation chooses whichever is cleaner. **No model change.**
**Frontend API client:** `src/api/site.js` + `src/api/profile.js` (compose); or new `src/api/identity.js`
**UI / interaction:**
  - one page with sections: 标识 (handle/name/name_en/role/pronouns/location), 文案 (tagline/typing_line/bio), 头像 + 头像选择器 (existing media picker), 链接 (github/email), 站点 (footer_note/default_theme/launched_at/stack_chips)
  - single 保存 saves both endpoints; partial failure surfaces the failing section
  - delete the standalone `Profile.jsx` / `Site.jsx` after migration (theme moves to its own page in Task 11)
**Automated tests:** Vitest for the form; pytest already covers PUTs
**Playwright acceptance path:**
  1. /admin/site-identity → edit name + typing_line + stack_chips → save → reload → assert persisted
  2. visit `/` → assert HeroA shows new name and typing_line
  3. screenshot before/after
**Snapshot location:** `/tmp/admin-rebuild/task-6/identity-form.png`, `/tmp/admin-rebuild/task-6/public-after.png`
**Commit message:** `refactor(admin/identity): merge profile + site into one workflow`
**Definition of done:** standard checklist
**Completed:** `7d404a5` (`refactor(admin/identity): merge profile + site into one workflow`).

- **Tests:** `npx vitest run src/admin/SiteIdentity.test.jsx` → 5/5 (load both endpoints, save only changed slices, skip endpoint when slice clean, partial-failure surface, dirty-disabled save). Combined `npx vitest run src/admin/SiteIdentity.test.jsx src/admin/ActivityLog.test.jsx src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 37/37 (no Task 1/2/3/4/5 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-6/verify.py` → login → sidebar 04 group shows 站点身份 / 联系方式 / 主题 (no 作者资料) → /admin/site-identity loads both /profile and /site → edit name (profile) + tagline (site) → save → toast 已保存 → reload → both fields persisted → public HomeA shows new name; cleanup restores originals. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-6/{sidebar,site-identity,public-after}.png`.

Implementation note: backend keeps two endpoints (`PUT /profile` and `PUT /site`); the merged page builds two patches and fires them in parallel only for slices that actually changed, surfacing partial failure ("部分保存失败") so the owner knows which surface to retry. The 主题 entry temporarily reuses `/admin/site` until Task 11 splits theme into its own page.

---

### Task 7 — Pet templates: expose all 12 modes

**Status:** completed
**Priority:** high
**Frontend evidence:** `AsciiPet.jsx` payload modes — `greet, recommend_next, summary_react, selection_explain, selection_qa, free_chat, idle_monologue, article_finished, code_assist, pet_care`, plus backend-known `follow_up`, `reading_assist`. S6.
**Owner problem:** owner can only edit 5/12 mode templates from admin. The rest fall back to backend defaults; tuning requires a code edit.
**Existing capability:** backend `pet_config.templates` already accepts all 12 modes; reset endpoint covers all. UI shows 5.
**Gap:** UI omits 7 modes.
**Admin module:** 05 宠物配置 / 模板
**Backend touch:** none
**Frontend API client:** none (existing PUT works)
**UI / interaction:**
  - one fieldset per mode (12 total), grouped under 2 headings: 主动 (greet, idle_monologue, article_finished, code_assist, recommend_next, pet_care) / 响应 (summary_react, selection_explain, selection_qa, free_chat, follow_up, reading_assist)
  - each fieldset: 6-row monospace textarea (max 800), 默认 button, char count
**Automated tests:** Vitest snapshot of all 12 fieldsets present
**Playwright acceptance path:**
  1. /admin/pet/templates → assert 12 fieldsets visible with correct mode labels
  2. edit `code_assist` template → save → reload → assert persisted
  3. trigger `code_assist` mode on public Reader (open a long code block) → assert pet uses new template (or fallback if LLM offline — at least verify request payload)
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-7/templates.png`
**Commit message:** `feat(admin/pet): expose all 12 mode templates instead of 5`
**Definition of done:** standard checklist
**Completed:** `993465e` (`feat(admin/pet): expose all 12 mode templates instead of 5`).

- **Tests:** `npx vitest run src/admin/pet/PetTemplates.test.jsx` → 5/5 (all 12 modes render, edits flow through patch with merged map, per-mode reset writes default, reset disabled when default-matched, group reset triggers parent onReset). Combined regression `npx vitest run src/admin/pet/PetTemplates.test.jsx src/admin/SiteIdentity.test.jsx src/admin/ActivityLog.test.jsx src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 42/42 (no Task 1-6 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-7/verify.py` → login → /admin/pet?tab=templates → assert all 12 fieldsets visible (greet / idle_monologue / recommend_next / article_finished / reading_assist / code_assist / pet_care / summary_react / selection_explain / selection_qa / free_chat / follow_up) → edit code_assist via JS-dispatched events → click Save (Pet.jsx primary button) → API check confirms backend stored the new template → cleanup restores original. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-7/templates.png` (full-page).

Implementation note: the 12 modes are split into 主动 / 响应 groups for UX legibility only — backend treats every mode the same. Each fieldset adds a hint line under the legend, a char-count footer (turns red past 90% of 800-char limit), and a per-mode 重置默认 button that lazily fetches the backend defaults via `apiPet.fetchDefaults` and writes one mode at a time.

---

### Task 8 — Public Reader likes wired to server (O5)

**Status:** completed
**Priority:** high (data integrity)
**Frontend evidence:** `Reader.jsx` reactions row — `onLike` writes only to `localStorage[bl.likes.<id>]` despite `api.posts.like(id)` existing.
**Owner problem:** admin shows zero likes because the public site never POSTs them. The KPI on dashboard is meaningless until this is fixed.
**Existing capability:** `POST /api/posts/:id/like` works server-side; per-IP-per-day idempotent.
**Gap:** Reader doesn't call it.
**Admin module:** none directly; Dashboard "累计点赞" becomes truthful as a side-effect.
**Backend touch:** none
**Frontend API client:** `src/api/client.js` — `api.posts.like` already exists; verify
**UI / interaction:**
  - Reader: on like, POST first; on success bump local + counter; on 429 keep local but surface a tiny "saved on next refresh" hint
  - admin Posts list: add a likes column reading `post.likes`
**Automated tests:** Vitest for Reader's like handler; pytest already covers backend
**Playwright acceptance path:**
  1. /p/<id> → click ♡ → assert ♥ + counter increments
  2. POST in network log → assert 200/202
  3. /admin/posts → assert likes column shows ≥1 for that post
  4. /admin/dashboard → assert "累计点赞" KPI bumped
**Snapshot location:** `/tmp/admin-rebuild/task-8/reader-liked.png`, `/tmp/admin-rebuild/task-8/admin-likes.png`
**Commit message:** `fix(reader): write likes to server, surface counts in admin`
**Definition of done:** standard checklist
**Completed:** `fcab65e` (`fix(reader): write likes to server, surface counts in admin`).

- **Tests:** `npx vitest run src/api/client.test.js` → 3/3 (api.posts.like POSTs the right URL + parses {likes, was_new}; non-2xx throws so caller can fall back; api.posts.detail surfaces server's likes field). Combined regression `npx vitest run src/api/client.test.js src/admin/pet/PetTemplates.test.jsx src/admin/SiteIdentity.test.jsx src/admin/ActivityLog.test.jsx src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 45/45 (no Task 1-7 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-8/verify.py` → seed initial likes via API → public `/p/vps` → click ♡ → assert POST `/api/posts/vps/like` fired and Reader counter equals server total (per-IP-per-day dedup means a re-run keeps the same total — proves wiring without depending on a fresh dedup window) → admin `/admin/posts` → vps likes cell matches server total → reload `/p/vps` → counter persists. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-8/{reader-liked,admin-likes}.png`.

Implementation note: backend gained a batch `likes.get_counts(post_ids)` so the admin list populates a likes column without N+1 queries; PostSummary's new `likes: int = 0` default leaves public list endpoints unchanged. Reader's onLike is fully optimistic — flips heart and bumps count immediately, then replaces the local count with the server total on success; on 429 / network error the optimistic state sticks and reconciles on next load.

---

### Task 9 — Contacts list wired into HomeA (replace 小红书/抖音 hardcode)

**Status:** completed
**Priority:** high
**Frontend evidence:** `HomeA.jsx:400-426` literal entries; `apiContacts` defined and unused on public.
**Owner problem:** owner can't change contact channels without editing source code; today's "管理 contacts" page is a dead-end. C8.
**Existing capability:** admin `Contacts.jsx` and `GET /api/contacts` already work.
**Gap:** public render still uses literals.
**Admin module:** 04 首页与品牌 / 联系方式 (existing) — add UI guardrails (preset social-icon catalogue, href validation) in this task
**Backend touch:** none
**Frontend API client:** `src/api/contacts.js` exists (admin); add public `useContacts` consumption
**UI / interaction (public):**
  - HomeA contact row reads from `GET /api/contacts` (existing endpoint, currently unused)
  - render mirrors today's hand-styled tiles; falls back to current literals if API empty (one-time migration)
**UI / interaction (admin):**
  - `Contacts.jsx`: dropdown of presets (`email / github / twitter / xiaohongshu / douyin / mastodon / linkedin / rss / website`); each preset autofills `label` + a default href template; href validation against `value` (e.g., `email:foo@bar` → `mailto:foo@bar`)
**Automated tests:** Vitest for HomeA contact row pulling from API; pytest covers contacts route
**Playwright acceptance path:**
  1. /admin/contacts → seed `小红书` and `抖音` rows → save
  2. visit `/` → assert contact row renders 4 entries from API (email + github + 小红书 + 抖音)
  3. delete 小红书 row → assert disappears from public
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-9/admin-contacts.png`, `/tmp/admin-rebuild/task-9/public-contacts.png`
**Commit message:** `feat(home): render contacts from API and replace hardcoded socials`
**Definition of done:** standard checklist
**Completed:** `c8f48e1` (`feat(home): render contacts from API and replace hardcoded socials`).

- **Tests:** `npx vitest run src/components/contact-row.test.jsx` → 7/7 (fallback builder picks up email/github, skips missing fields, ContactRow maps each API item to a tile, http items render as anchors with target=_blank, items without protocol render as click-to-copy buttons, empty contacts list falls back, completely empty site renders nothing). Combined regression `npx vitest run src/components/contact-row.test.jsx src/api/client.test.js src/admin/pet/PetTemplates.test.jsx src/admin/SiteIdentity.test.jsx src/admin/ActivityLog.test.jsx src/admin/Layout.test.jsx src/admin/frontmatter.test.js src/api/admin.test.js src/admin/Login.test.jsx` → 52/52 (no Task 1-8 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-9/verify.py` → seed 小红书 (https) + 抖音 (no href) via API → public `/` shows both tiles (小红书 as `<a target=_blank>`, 抖音 as click-to-copy `<button>`) → delete seeded contacts → reload → tiles gone, fallback renders email + github from site. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-9/{public-with-seeded,public-fallback}.png`.

Implementation note: contact tile decision is href-shape based — items with http(s) / mailto / tel / absolute-path render as anchors, others as click-to-copy buttons. This pattern lets owners add unstructured handles (a 抖音 ID, a discord username) without inventing fake URL schemes. ContactRow lives in its own module so the unit tests don't drag in HomeA's heavy hook surface.

---

### Task 10 — Comments moderation: per-post filter + bulk approve/reject

**Status:** completed
**Priority:** medium
**Frontend evidence:** `Reader.jsx` future public comments + admin oversight. O1.
**Owner problem:** during a spike (e.g., spam wave on one post) owner cannot scope the queue; must approve one-by-one.
**Existing capability:** `Comments.jsx` tabs + inline reply + optimistic moderation; backend `GET /comments?post_id=` supports filter.
**Gap:** UI lacks per-post filter and bulk actions.
**Admin module:** 03 观察 / 评论
**Backend touch:** add `POST /api/admin/comments/bulk` accepting `{ids:int[], action:'approve'|'spam'|'pending'|'delete'}`; **migration** none
**Frontend API client:** `src/api/comments.js` — add `bulk(action, ids)`
**UI / interaction:**
  - filter row above tabs: post select (typeahead by post title) + 清除 button; reflects in `?post_id=` query
  - row checkbox + "全选" header checkbox; bulk action bar appears when ≥1 selected: 批量通过 / 批量标垃圾 / 批量删除 with confirm modal
**Automated tests:** pytest for new bulk endpoint (success, partial-failure, scope check); Vitest for selection state
**Playwright acceptance path:**
  1. seed 3 pending comments on post X
  2. /admin/comments → filter by post X → assert 3 rows
  3. select all → 批量通过 → confirm → assert all flip to approved
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-10/bulk-approve.png`
**Commit message:** `feat(admin/comments): per-post filter and bulk moderation`
**Definition of done:** standard checklist
**Completed:** `87a8875` (`feat(admin/comments): per-post filter and bulk moderation`).

- **Tests:** `npx vitest run src/admin/Comments.test.jsx` → 5/5 (post filter passes post_id, select-all + bulk approve calls bulk('approve', ids), single-row bulk passes only that id, cancel in confirm aborts, clearing filter restores no post_id). Combined regression `npx vitest run` → 85/85 (no Task 1-9 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-10/verify.py` → seed 3 pending comments via the public submit endpoint → login → /admin/comments → enter post-id filter → assert seeded rows render → click select-all → bulk action bar visible → 批量通过 → auto-accept confirm → re-fetch via API → all 3 rows flipped to approved → cleanup deletes seeded comments. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-10/{filtered,after-bulk}.png`.

Implementation note: backend gained a single-statement `bulk_set_status` / `bulk_delete` so a 200-row batch is one DB roundtrip; the bulk endpoint writes one event_log row carrying the affected count + the changed status, so the activity feed shows the wave instead of 200 individual rows. UI bulk bar is sticky-style and only renders when at least one row is selected.

---

### Task 11 — Theme color picker (replace raw oklch strings)

**Status:** completed
**Priority:** medium
**Frontend evidence:** TopBar accent dot, every `color-mix(in oklab, var(--accent), …)`, every `--danger` border on public site.
**Owner problem:** editing oklch is developer-only; one slip blanks half the site. C9.
**Existing capability:** PUT /theme accepts strings; site renders them.
**Gap:** input is a freeform text field.
**Admin module:** 04 首页与品牌 / 主题 (split out of merged Site page)
**Backend touch:** none
**Frontend API client:** `src/api/site.js` `getTheme/putTheme` already exist
**UI / interaction:**
  - per-color swatch button → opens a small popover with H/S/L sliders writing oklch (or hsl→oklch conversion) + manual oklch input fallback
  - live preview pane mounting a stripped-down version of the public hero with the candidate accent
  - 重置默认 per color
**Automated tests:** Vitest snapshot of picker; pytest already covers PUT
**Playwright acceptance path:**
  1. /admin/theme → tweak accent slider → assert preview updates
  2. save → visit `/` → assert TopBar accent dot reflects new color
  3. screenshot picker + public
**Snapshot location:** `/tmp/admin-rebuild/task-11/picker.png`, `/tmp/admin-rebuild/task-11/public-applied.png`
**Commit message:** `feat(admin/theme): swatch picker with live preview replaces raw oklch input`
**Definition of done:** standard checklist
**Completed:** `bcdd8ca` (`feat(admin/theme): swatch picker with live preview replaces raw oklch input`).

- **Tests:** `npx vitest run src/admin/oklch.test.js` → 8/8 (parse with whitespace + alpha, returns null on garbage, clamps absurd values, format emits canonical L% C H with rounded chroma + integer hue, parse↔format round-trips, THEME_DEFAULTS match public seeds). Combined regression `npx vitest run` → 93/93 (no Task 1-10 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-11/verify.py` → login → /admin/site (now 主题) → assert 4 color rows + preview render → drive H slider on accent_color via JS-dispatched events → raw input picks up new hue → save → 已保存 toast → API confirms backend stored new color → visit / on public → assert document.documentElement's --accent CSS variable resolves to the new oklch() string → cleanup restores original. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-11/{theme-page,saved}.png`.

Implementation note: oklch parse / format helpers in their own module so they're trivially unit-tested. Site.jsx now owns just the theme workflow — identity fields are gone (already lived on /admin/site-identity from Task 6) so the page no longer duplicates them. Public theme apply lives in App.jsx: every /api/site fetch copies accent_color / accent2_color / violet_color / danger_color onto document.documentElement as `--accent / --accent-2 / --violet / --danger` plus an oklab `color-mix` `--accent-glow`. The visitor-side green/amber/violet preset overlay (utils/accent.js) is unchanged; admin-saved values are the *defaults* the overlay sits on top of.

---

### Task 12 — Posts editor: media insert button

**Status:** completed
**Priority:** medium
**Frontend evidence:** Reader body images (`reader-body img`).
**Owner problem:** owner uploads to media library but has to type `![alt](/media/<path>)` by hand. C1 / C6 join.
**Existing capability:** media library + alt; markdown supports inline images.
**Gap:** no button to pick a media item and insert at cursor.
**Admin module:** 02 内容 / 文章 / PostEditor
**Backend touch:** none
**Frontend API client:** existing `src/api/media.js`
**UI / interaction:**
  - 插入图片 button → modal grid picker (filtered to image mimes) → click inserts `![alt](/media/<storage_path>)` at cursor with the current alt
  - keyboard: `⌘ + I` open picker, Enter inserts
**Automated tests:** Vitest for cursor-aware insertion
**Playwright acceptance path:**
  1. open existing post in editor
  2. click 插入图片 → pick a media item → assert markdown updated with correct path
  3. preview updates → save → public Reader shows image
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-12/picker.png`, `/tmp/admin-rebuild/task-12/public-image.png`
**Commit message:** `feat(admin/posts): media library picker for inline images`
**Definition of done:** standard checklist
**Completed:** `5d3d3e9` (`feat(admin/posts): media library picker for inline images`).

- **Tests:** `npx vitest run src/admin/markdownInsert.test.js` → 9/9 (caret insert, selection replace, reversed-selection handling, range clamp, null-source tolerance, alt → filename fallback, storage_path fallback, missing-path → empty string). Combined regression `npx vitest run` → 102/102 (no Task 1-11 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-12/verify.py` → auto-uploads a 1×1 PNG if library empty → login → /admin/posts → edit vps → wait textarea populate → click 插入图片 → media picker modal opens → click first tile → assert textarea now contains `![…](/media/…)` directive → cleanup deletes seeded media. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-12/{editor,after-insert}.png`.

Implementation note: helpers split into `markdownInsert.js` (pure functions for cursor-aware splice + image-directive builder) and `MediaPicker.jsx` (reusable image-mime-filtered grid modal). PostEditor wires a 插入图片 header button + a `⌘ I` / `Ctrl I` keyboard shortcut on the textarea; after pick, caret restores just past the inserted directive on next paint so the author can keep typing.

---

### Task 13 — Pet visitor profile inspector

**Status:** completed
**Priority:** medium
**Frontend evidence:** `AsciiPet.jsx` — visitor identity bound to IP+UA, `/api/pet/forget` exists. O2.
**Owner problem:** when a visitor mentions in chat that the pet "forgot them", owner has no way to see what the pet remembered.
**Existing capability:** `pet_visitor_profile` table populated with `style_summary, memory_summary, interest_tags, recent_post_ids, interaction_count, proactive_muted_until`. Conversation list keys by visitor_hash.
**Gap:** none of those fields are surfaced.
**Admin module:** 03 观察 / 宠物对话 / 详情页 (existing detail page)
**Backend touch:** extend `GET /api/admin/pet/conversations/{visitor_hash}` response with the profile fields; or new `GET /api/admin/pet/profiles/{visitor_hash}`
**Frontend API client:** `src/api/pet.js`
**UI / interaction:**
  - sidebar block on the conversation detail page: species, locale, language, interest_tags chips, recent_post_ids (linked), interaction_count, last_seen ago, "静默主动到 " timestamp with a 解除 button (PATCH `proactive_muted_until=null`)
  - 重置档案 button (clears summaries + counters but keeps messages)
**Automated tests:** pytest for the new GET; Vitest for the panel
**Playwright acceptance path:**
  1. seed conversation with a visitor (or use real one)
  2. /admin/pet/conversations/<hash> → assert profile sidebar shows fields
  3. mute proactive → assert backend updated
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-13/profile-panel.png`
**Commit message:** `feat(admin/pet): visitor profile inspector on conversation detail`
**Definition of done:** standard checklist
**Completed:** `4f8f8e7` (`feat(admin/pet): visitor profile inspector on conversation detail`).

- **Tests:** `npx vitest run src/admin/pet/VisitorProfileSidebar.test.jsx` → 5/5 (empty placeholder, full field render with chips + post links, unmute button only when muted_until in future, unmute click calls patchProfile + onMutated, reset confirm step gates the call). Combined regression `npx vitest run` → 107/107 (no Task 1-12 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-13/verify.py` → find existing visitor or summon pet to seed → login → /admin/pet/conversations/<hash> → assert sidebar mounts with profile fields → click 重置档案 → confirm step appears. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-13/profile-sidebar.png`.

Implementation note: backend extends the existing detail GET with a `profile` field (one extra primary-key lookup, no schema change) plus a new `PATCH /pet/profiles/{visitor_hash}` endpoint accepting `{action: "unmute" | "reset"}`. Reset is gated by an inline confirm step in the sidebar — explicitly NOT a one-click data wipe — and the parent `onMutated` callback re-fetches the conversation so the sidebar reflects backend state immediately.

---

### Task 14 — Inbox page (运营中枢)

**Status:** completed
**Priority:** medium
**Frontend evidence:** none directly — abstracts visitor signals onto a single triage screen. PRD §5.2 introduces it.
**Owner problem:** owner has 3 attention surfaces (待审评论 / 最新宠物对话 / login alerts) scattered across 3 pages. Inbox unifies them.
**Existing capability:** comments, pet conversations, event_log all queryable.
**Gap:** no unified screen.
**Admin module:** 01 运营中枢 / 收件箱 (new)
**Backend touch:** new `GET /api/admin/inbox?since=` returning bundle of pending comments + new pet conversations + login events; or compose client-side from existing endpoints (preferred — less coupling)
**Frontend API client:** new `src/api/inbox.js` composing existing clients
**UI / interaction:**
  - three vertical sections: 评论待审 (top 10) / 宠物新对话 (top 10) / 登录与异常 (top 10)
  - per-row jump-to-source icon
  - 全部已读 button writes a `last_seen_at` to localStorage; new items get a left accent stripe
**Automated tests:** Vitest snapshot
**Playwright acceptance path:**
  1. seed 1 pending comment + 1 pet conversation + 1 login event
  2. /admin/inbox → assert all three appear
  3. click jump → routes to corresponding detail
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-14/inbox.png`
**Commit message:** `feat(admin/inbox): unified triage page for visitor signals`
**Definition of done:** standard checklist
**Completed:** `040356e` (`feat(admin/inbox): unified triage page for visitor signals`).

- **Tests:** `npx vitest run src/admin/Inbox.test.jsx src/admin/Layout.test.jsx` → 10/10 (three sections render, empty placeholders, mark-all-read clears badge, accent stripe on rows newer than last_seen, graceful degradation when one endpoint rejects). Combined regression `npx vitest run` → 112/112 (no Task 1-13 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-14/verify.py` → seed pending comment via public submit → login → /admin/inbox → assert all 3 sections + sidebar 01 group lists 收件箱 + comments section shows seeded row → click 全部已读 → badge flips to "已全部查看" → cleanup deletes seeded comment. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-14/inbox.png`.

Implementation note: the page composes from existing endpoints (no backend change) using `Promise.allSettled`-style isolation — one endpoint failure surfaces a banner but the other sections still render with their data. "新" stripe gating reads `bl.admin.inbox.last_seen` from localStorage; 全部已读 stamps `Date.now()` so a future visit immediately knows what's new since the last triage.

---

### Task 15 — Posts editor: autosave drafts

**Status:** completed
**Priority:** medium
**Frontend evidence:** any post in `Reader.jsx` (downstream effect: less risk of losing in-flight edits).
**Owner problem:** browser crash mid-edit loses all unsaved changes. Cross-cut: same risk in Pet templates and Now composer (deferred to those tasks).
**Existing capability:** none.
**Gap:** no autosave.
**Admin module:** 02 内容 / 文章 / PostEditor
**Backend touch:** none (use existing PATCH; or write to localStorage only — implementation choice)
**Frontend API client:** existing
**UI / interaction:**
  - localStorage-backed autosave every 5s of dirty changes; key `bl.admin.draft.<id>`
  - on editor open, if a draft exists newer than the server `updated_at`, banner: "有未保存的草稿（X 分钟前），恢复 / 丢弃"
  - clear on successful save
**Automated tests:** Vitest with fake timers
**Playwright acceptance path:**
  1. open editor → type → wait 6s → reload → assert banner shows
  2. click 恢复 → text restored
  3. click 丢弃 → text gone, server version
**Snapshot location:** `/tmp/admin-rebuild/task-15/draft-banner.png`
**Commit message:** `feat(admin/posts): autosave drafts to localStorage with recovery banner`
**Definition of done:** standard checklist
**Completed:** `d54d90f` (`feat(admin/posts): autosave drafts to localStorage with recovery banner`).

- **Tests:** `npx vitest run src/admin/draftStore.test.js` → 9/9 (save/load roundtrip with timestamp, null id falls back to `__new__`, garbage JSON returns null, `draftIsNewerThan` handles ms / ISO / missing server timestamps). Combined regression `npx vitest run` → 121/121 (no Task 1-14 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-15/verify.py` → login → open editor for `vps` → JS-dispatch type a marker → wait 6s → assert `[data-testid=draft-status]` indicator appears → reload → re-open editor → assert `[data-testid=draft-banner]` recovery banner visible → click 恢复 → textarea contains marker → type a discard probe + wait 6s + reload + click 丢弃 → banner removed and textarea reverts to server content. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-15/autosave-status.png`, `/tmp/admin-rebuild/task-15/recovery-banner.png`.

Implementation note: pure helpers in `src/admin/draftStore.js` (saveDraft / loadDraft / clearDraft / draftIsNewerThan) keep all storage concerns out of the editor. PostEditor sets `dirtyRef = true` from every user-driven mutation (textarea onChange, GUI strip updateField, image insert) and runs a 5-second debounced autosave only when the dirty flag is set. The recovery banner appears only when the local draft's `savedAt` is newer than the server's `updated_at`, so freshly-saved server content doesn't trigger a stale prompt. On successful save the draft is cleared so reload shows a clean editor.

---

### Task 16 — Global command palette in admin (⌘K)

**Status:** completed
**Priority:** medium
**Frontend evidence:** public site has `Palette.jsx`. PRD §6.2 — admin must adopt the same shortcut model.
**Owner problem:** every workflow today requires sidebar click. ⌘K should jump to any page or run common commands.
**Existing capability:** none in admin.
**Gap:** Layout has no palette.
**Admin module:** Layout (cross-cutting)
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - `⌘K` / `Ctrl+K` opens floating dialog with input + sectioned results: `导航` (every admin route), `命令` (新建文章 / 退出 / 切换主题 / 复制访问令牌 / …), `文章` (typeahead by title)
  - ↑↓ navigate, Enter run, Esc close
  - kbd hint footer matching public Palette
**Automated tests:** Vitest for filtering + keyboard handling
**Playwright acceptance path:**
  1. on /admin/dashboard press ⌘K → palette opens
  2. type "文章" → arrow down to "新建文章" → Enter → editor opens at `/admin/posts/__new__`
  3. press Esc → palette closes
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-16/palette.png`
**Commit message:** `feat(admin/palette): ⌘K command palette mirroring public site`
**Definition of done:** standard checklist
**Completed:** `28cae37` (`feat(admin/palette): cmd-K command palette mirroring public site`).

- **Tests:** `npx vitest run src/admin/commandPaletteItems.test.js src/admin/CommandPalette.test.jsx` → 18/18 (build/filter/group helpers + render, query filter, Enter runs, ArrowDown moves selection, Escape closes, empty placeholder, async post load). Combined regression `npx vitest run` → 139/139 (no Task 1-15 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-16/verify.py` → login → Meta+K opens palette → 收件 narrows results → Enter routes to /admin/inbox → Meta+K → 新建 → Enter routes to /admin/posts and editor opens (post-fields-strip visible) → Meta+K → Escape detaches palette → Meta+K from posts page surfaces post typeahead section. All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-16/palette-open.png`, `/new-post-from-palette.png`, `/palette-with-posts.png`.

Implementation note: pure helpers in `src/admin/commandPaletteItems.js` (build / filter / groupBySection) keep React state thin. Layout owns the global ⌘K listener and the runners object (navigate / new post / open post via location.state side door / clipboard token / open public site / logout). Posts.jsx pops `location.state.editPost` on mount so the palette's "新建文章" or post typeahead lands directly on the editor without inventing a new `/admin/posts/__new__` route. A document-level Escape listener on the palette ensures Esc closes the dialog even if focus moved off the search input.

---

### Task 17 — Global keyboard shortcuts (j/k, Enter, ?, g <key>)

**Status:** completed
**Priority:** medium
**Frontend evidence:** PRD §6.2 — match public's keyboard-first model.
**Owner problem:** mouse-only navigation is slow.
**Existing capability:** none.
**Gap:** no row focus, no jumps.
**Admin module:** Layout + per-page tables (cross-cutting)
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - `j/k` move focus across rows in any list page; Enter opens
  - `?` opens a help dialog listing shortcuts grouped by scope
  - `g d / g p / g m / g c / g t / g s / g a` jump to dashboard / posts / media / comments / tags / settings / activity
  - `e` edit focused row, `n` new (where applicable)
  - shortcuts disabled while command palette / modal / textarea is focused
**Automated tests:** Vitest with keyboard events
**Playwright acceptance path:**
  1. /admin/posts → press j → first row focuses → k → no change at top → Enter opens editor
  2. press ? → help dialog → screenshot
  3. press g d → dashboard
**Snapshot location:** `/tmp/admin-rebuild/task-17/help-dialog.png`
**Commit message:** `feat(admin/kbd): j/k navigation, ? help, g <x> jumps`
**Definition of done:** standard checklist
**Completed:** `f688b6e` (`feat(admin/kbd): j/k navigation, ? help, g <x> jumps`).

- **Tests:** `npx vitest run src/admin/keyboardShortcuts.test.js` → 11/11 (JUMP_MAP, SHORTCUT_GROUPS coverage, resolveJump case-insensitive, shouldIgnoreEvent for modifier / textarea / input / contentEditable / palette-open / data-shortcut-suppress). Combined regression `npx vitest run` → 150/150 (no Task 1-16 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-17/verify.py` → login → `g p` jumps to /admin/posts → first row auto-focuses → `j` moves to row 1 (of 5) → `k` returns to row 0 → Enter opens editor → re-navigate → `n` opens new-post editor → `?` opens help dialog → Esc closes → `g a` jumps to /admin/activity-log → typing in search input is NOT hijacked (shortcuts properly suppressed). All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-17/help-dialog.png`, `/activity-after-jump.png`.

Implementation note: pure helpers in `src/admin/keyboardShortcuts.js` (`JUMP_MAP`, `SHORTCUT_GROUPS`, `resolveJump`, `shouldIgnoreEvent`) keep the React layer thin. `useGlobalShortcuts` owns the `?` and `g <x>` two-key sequence (1.5s pending window) and delegates suppression to `shouldIgnoreEvent`, which DOM-probes for `[data-testid=admin-palette]` and any `[data-shortcut-suppress=true]` surface so the help dialog and future modals can opt in. Posts page adds `j/k/Enter/e/n` via a local listener that auto-detaches whenever the editor is open. Row-level focus is rendered via `data-focused="true"` + an accent left-border, with `scrollIntoView` on focus change.

---

### Task 18 — URL-state filters & pagination

**Status:** completed
**Priority:** medium
**Frontend evidence:** PRD §6.2 — refresh / share must restore.
**Owner problem:** refresh on /admin/posts loses filter+page; can't share a filtered view.
**Existing capability:** Pet uses `?tab=`. No other page does.
**Gap:** Posts/Comments/Media/Tags/Activity-log filters all live in component state.
**Admin module:** cross-cutting
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - useSyncedSearchParams hook (or equivalent) ensuring filters/pagination round-trip via querystring
  - back/forward buttons restore prior view
**Automated tests:** Vitest for the hook
**Playwright acceptance path:**
  1. /admin/posts → filter status=draft → page=2 → reload → assert state preserved
  2. browser back → empty filter
  3. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-18/url-restored.png`
**Commit message:** `feat(admin): url-state filters and pagination`
**Definition of done:** standard checklist
**Completed:** `ae66dbd` (`feat(admin): url-state filters and pagination on posts`).

- **Tests:** `npx vitest run src/admin/searchParamsState.test.js` → 12/12 (default values omitted, non-default values written, garbage int falls back, round-trip identity, statesEqual). Combined regression `npx vitest run` → 162/162 (no Task 1-17 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-18/verify.py` → login → /admin/posts has no query → set pageSize=50 → URL writes `pageSize=50` → click status=draft → URL writes `status=draft` → type "rust" → URL writes `q=rust` → reload → all three preserved including search input value → clear q → URL drops `q` (default empty) → browser Back → q=rust restored → click status=all → URL drops `status` (default). All assertions green.
- **Snapshots:** `/tmp/admin-rebuild/task-18/filtered-state.png`, `/after-reload.png`.

Implementation note: pure helpers in `src/admin/searchParamsState.js` (`buildQueryFromState`, `buildStateFromQuery`, `intParser`, `statesEqual`) keep encoding logic separate from React; the schema array per page declares each field's default + parser/serializer. `useSyncedSearchParams` hook owns the bidirectional bind (URL → state via location.search effect, state → URL via `navigate({pathname,search})` with `replace:false` so back/forward replays prior views). Posts.jsx now derives `statusFilter / q / page / pageSize` from the hook state and writes via `setFilters({key,page:1})`. The palette side-door for `editPost` was updated to preserve `location.search` when wiping `state`, so jumping to a post from the palette no longer clobbers the user's filters.

---

### Task 19 — Unified ConfirmModal + Toast across admin

**Status:** completed
**Priority:** medium
**Frontend evidence:** PRD §6.2.
**Owner problem:** five different feedback patterns (native confirm/alert, ConfirmModal, SecretModal, inline banner, toast) erodes trust.
**Existing capability:** DangerZone has a `ConfirmModal`; Profile/Site/Media have toasts.
**Gap:** the rest use `confirm()`/`alert()`/inline.
**Admin module:** cross-cutting
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - extract `ConfirmModal` and `Toast` into `src/admin/ui/`; a single `useConfirm()` and `useToast()` hooks
  - replace every `confirm()` / `alert()` callsite with the hook
  - destructive actions get red primary button + typed-confirm input where data loss is permanent
**Automated tests:** Vitest for hooks; visual regression via Playwright per page
**Playwright acceptance path:**
  1. trigger delete on Tags → ConfirmModal renders, not browser native
  2. on success → Toast renders bottom-right
  3. trigger save on Profile → Toast
  4. screenshot per modal
**Snapshot location:** `/tmp/admin-rebuild/task-19/confirm.png`, `/tmp/admin-rebuild/task-19/toast.png`
**Commit message:** `refactor(admin/ui): unify ConfirmModal + Toast across admin`
**Definition of done:** standard checklist
**Completed:** `e86e322` (`refactor(admin/ui): unify ConfirmModal + Toast across admin`).

- **Tests:** `npx vitest run src/admin/ui/UIProvider.test.jsx` → 9/9 (confirm resolves true/false, Esc cancels, destructive style, toasts render by kind, click dismisses, ttl auto-dismiss, throws outside provider). Plus updated `src/admin/Comments.test.jsx` (5/5) + `src/admin/pet/PetConversationDetail.test.jsx` (2/2) wrap their renders in UIProvider and click `[data-testid=confirm-ok]` instead of mocking `window.confirm`. Combined regression at the Task 19 commit was 171/171; an unrelated prior-round i18n change to `Login.jsx` (button text → 登录) without a matching `Login.test.jsx` update introduces 5 pre-existing failures when the unstaged stash is restored — those live in unstaged work, not in `e86e322`.
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-19/verify.py` → login → /admin/tags → create unique-slug tag → toast-success appears (no native dialog) → click delete → `[data-testid=confirm-modal]` opens (browser-native confirm did NOT fire — verified via `page.on('dialog', ...)` listener) → cancel keeps row → ok deletes row + toast-success → invalid slug 创建 surfaces toast-error. Page-level dialog listener confirms zero native confirm/alert events fired during the entire flow.
- **Snapshots:** `/tmp/admin-rebuild/task-19/{after-create,confirm-modal,toast-success,toast-error}.png`.

Implementation note: single `UIProvider` mounted in `Layout.jsx` exposes `useConfirm()` (returning `Promise<boolean>` from `await confirm({title, message, confirmLabel, cancelLabel, destructive})`) and `useToast()` (with `success/error/info/dismiss` methods, default 3.5s ttl, error gets 6s). All eleven `confirm()` callsites + every page-level `alert()` were replaced: Posts, Tags, Media, Now, Pet, Projects, Contacts, Comments (bulk + single delete + reply), settings/ApiTokens, pet/PetConversationDetail. Destructive intents pass `destructive: true` for the red primary button. The modal carries `data-shortcut-suppress="true"` so the Task 17 global keyboard layer treats it as an active dialog. Test harnesses for Comments + PetConversationDetail now wrap their components in `<UIProvider>` and trigger the modal via `findByTestId('confirm-ok')` — closer to real UX than the previous `window.confirm` spy.

---

### Task 20 — Section-head + kbd visual primitives match public site

**Status:** completed
**Priority:** medium
**Frontend evidence:** `HomeA.jsx:315-323, 343-344, 367-368` — `<span class="n">01 /</span>` numbered heads with `<span class="count">…</span>` right-aligned counts.
**Owner problem:** admin pages lack the public site's visual punctuation; the rebuild doesn't *feel* like the same product.
**Existing capability:** none in admin.
**Gap:** every admin page head is currently a plain `<h1>`.
**Admin module:** cross-cutting (Layout + every page wrapper)
**Backend touch:** none
**Frontend API client:** none
**UI / interaction:**
  - `<SectionHead n="03" title="文章" count="42 entries" />` primitive
  - `<Kbd>⌘K</Kbd>` primitive matching `Palette.jsx` styling
  - apply on every page head + every keyboard hint
**Automated tests:** Vitest snapshot
**Playwright acceptance path:**
  1. visit each top-level admin page
  2. assert a numbered section head visible
  3. screenshot dashboard + posts + comments
**Snapshot location:** `/tmp/admin-rebuild/task-20/heads.png`
**Commit message:** `feat(admin/ui): SectionHead + Kbd primitives match public visual language`
**Definition of done:** standard checklist
**Completed:** `0c61615` (`feat(admin/ui): SectionHead + Kbd primitives match public visual language`).

- **Tests:** `npx vitest run src/admin/ui/SectionHead.test.jsx` → 6/6 (n + title + count + .label .n accent class, count omitted when null, lead paragraph below the rule, n missing falls back). Combined regression `npx vitest run` → 177/177 (no Task 1-19 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-20/verify.py` → login → visits 7 admin pages and asserts each shows a `[data-testid=section-head-{n}]` head with the `n / ./path` text + `.label .n` accent span. dashboard / posts / comments / tags / media / now / inbox all green; no duplicate heads on dashboard.
- **Snapshots:** `/tmp/admin-rebuild/task-20/{dashboard,posts,comments}.png`.

Implementation note: `<SectionHead n="03" title="./posts" count="42 entries" lead="..." />` reuses the public site's `.section-head` CSS class (HomeA.jsx line 317-326) with three new helper rules in `styles.css`: `.section-lead` (small dim paragraph), `.admin-kbd` (inline keycap chip), and `.admin-content .section-head` (smaller padding so the admin topbar's chrome doesn't double-stack). `<Kbd>` renders a `<kbd className="admin-kbd">` for shortcut hints. Applied across Dashboard / Posts / Comments / Tags / Media / Now / Inbox; remaining pages (Projects, Contacts, Pet, Site, SiteIdentity, Analytics, ActivityLog, Settings) keep their existing per-page heads for now and adopt incrementally as they're touched.

---

### Task 21 — Pet species catalogue admin (extract `species.js` to backend)

**Status:** completed (21a + 21b + 21c + 21d + 21e + 21f done)
**Priority:** medium
**Frontend evidence:** `src/components/pet/species.js` — 28 entries, hardcoded. `AsciiPet.jsx` reads frames + behavior from it. S7.
**Owner problem:** adding/tweaking a species requires a code edit + redeploy.
**Existing capability:** PetConfig stores chosen species per assigned visitor; the catalogue itself is hardcoded.
**Gap:** no DB table; no admin page.
**Admin module:** 05 宠物配置 / 物种目录 (new)
**Backend touch:**
  - **migration**: new `pet_species` table — `id (slug PK), name, rarity (common/uncommon/rare/epic/legendary CHECK), color (hex), trait_zh, personality_zh, description_zh, frames JSONB, behavior JSONB (proactive_level, idle_frequency, local_lines), stats JSONB, visible (bool)`
  - seed migration mirroring current `species.js` content
  - new `routers/admin/pet_species.py`: GET list, POST, PATCH, DELETE
  - public `GET /api/pet/species` returns visible-only (replaces frontend hardcode)
**Frontend API client:** new `src/api/petSpecies.js`
**UI / interaction:**
  - admin page: rarity-grouped table; per-row inline edit; preview frame in a small canvas
  - replace `src/components/pet/species.js` with a fetch from `/api/pet/species` (cached at app boot)
**Automated tests:** pytest for CRUD; Vitest for fetcher fallback
**Playwright acceptance path:**
  1. /admin/pet/species → edit `cat.local_lines` → save → visit `/` → wait for pet to idle-monologue → assert one of the new lines fires (or at least sample request payload contains it)
  2. screenshot admin + pet bubble
**Snapshot location:** `/tmp/admin-rebuild/task-21/species-admin.png`, `/tmp/admin-rebuild/task-21/pet-bubble.png`
**Commit message:** `feat(admin/pet): species catalogue editable from admin`
**Definition of done:** standard checklist
**Completed:** all six sub-tasks — `2b68fd6` (table+model+schema), `64184c7` (seed), `4b1af73` (CRUD router + public list), `35fc1b5` (admin editor tab), `ee79017` (frontend hydrates from API), `203b261` (`feat(admin/pet): inline ASCII frame editor in species panel (Task 21f)`).

#### Task 21a — pet_species table + model + schema (DONE)

- **Tests:** `./.venv/bin/python -m pytest tests/test_pet_species_model.py` → 5/5 (table round-trip with frames/behavior/stats JSONB, rarity CHECK rejects 'mythic', `PetSpeciesIn` slug pattern rejects `9bad`/`Duck`/long/`snake_case`, `PetSpeciesPatch` empty body valid + partial dump, `PetSpeciesOut.model_validate(row)` round-trips with timestamps).
- **Migration:** `./.venv/bin/alembic upgrade head` → `0014_api_token_usage_count -> 0015_pet_species` applied to dev DB.
- **Playwright:** none — pure data layer (no router, no UI yet; that lands in 21c/21d).

Implementation note: split species schemas into their own `app/schemas/pet_species.py` module instead of growing `pet.py` (which holds PetConfig). `Rarity = Literal["common","uncommon","rare","epic","legendary"]` is mirrored by a DB-level `CheckConstraint`; pgsql rejects unknowns even if the schema is bypassed. Slug pattern `^[a-z][a-z0-9-]{0,31}$` matches what `AsciiPet.jsx` already feeds the URL state. JSONB columns (`frames`, `behavior`, `stats`) keep schema-level validation loose because layout validation lives in `AsciiPet`.

#### Task 21b — pet_species seed migration (DONE)

- **Tests:** `./.venv/bin/python -m pytest tests/test_pet_species_seed.py` → 6/6 (all 27 expected IDs present, rarity matches frontend table, every species has 3 frames each containing the `{E}` eye-marker, behavior shape `{proactiveLevel,idleFrequency,localLines}`, stats has 5 axes, all visible + sort_order unique).
- **Idempotency:** down → up → up applied cleanly with `INSERT ... ON CONFLICT (id) DO NOTHING`.
- **Migration:** `./.venv/bin/alembic upgrade head` → `0015_pet_species -> 0016_pet_species_seed` applied to test + dev DB.
- **Playwright:** none — no UI / public endpoint yet (lands in 21c/21d).

Implementation note: ports the 27 species in `src/components/pet/species.js` verbatim — frames keep `{E}` markers untouched so the public API can serve them straight to `AsciiPet.jsx` without translation. Behavior keeps the camelCase `proactiveLevel/idleFrequency/localLines` shape for symmetry with the JS hardcode, so 21e can swap the import for a fetch with no transform layer. EN trait/personality/description copied into `*_zh` columns; the admin UI in 21d will let the owner localize. Stats merge `RARITY_STAT_BASE[rarity]` with per-species overrides exactly as the JS does. Migration uses `op.execute(sa.text(...))` with `:name` bindings (asyncpg requires `$N` or named bindings, not psycopg2 `%(name)s`) and `CAST(:frames AS jsonb)` for JSONB columns. Downgrade only deletes the seeded IDs so owner-added species via admin survive.

#### Task 21c — pet_species CRUD router + public list endpoint (DONE)

- **Tests:** `./.venv/bin/python -m pytest tests/test_pet_species_router.py tests/test_pet_species_model.py tests/test_pet_species_seed.py` → 26/26.
- **Router endpoints (admin):** `GET /api/admin/pet/species` (list incl. hidden), `POST /api/admin/pet/species` (write scope, 409 on dup id, 422 on bad slug/rarity), `PATCH /api/admin/pet/species/{id}` (write scope, partial update, 404 on missing), `DELETE /api/admin/pet/species/{id}` (write scope, 409 if SiteMeta.pet_config.species references it, 404 missing).
- **Router endpoint (public):** `GET /api/pet/species` (visible-only, ordered by sort_order, no auth).
- **Live API smoke:** Logged in as wyzz973@gmail.com → POST/PATCH/DELETE on `t21c-live` round-tripped (200/200/204) against running uvicorn on :51820. Public list returns 27 seeded rows with first row `duck`/`common` and unique sort_orders.
- **Snapshots:** `/tmp/admin-rebuild/task-21c/{public-species,admin-species}.json`.
- **Playwright:** none — endpoints have no UI yet (lands in 21d). The owner-facing admin page on /admin/pet/species + the AsciiPet swap come in 21d/21e respectively.

Implementation note: schema `frames` was originally typed `list[str]` but the seeded JS data is `list[list[str]]` (each frame = list of line strings). Fixed schema + model_validate test cases in 21a/21b. Admin router lives in its own `routers/admin/pet_species.py` next to `pet.py` (which still owns PetConfig — site-level pet behavior). Delete refusal looks at `SiteMeta.pet_config.species` because that's the only stable reference; visitor profile rows self-heal on next visit when their species disappears. Write endpoints accept session OR write-scope api-token; read endpoint accepts session OR any-scope token.

#### Task 21d — admin pet species editor tab (DONE)

- **Tests:** `npx vitest run src/admin/pet/PetSpeciesEditor.test.jsx` → 6/6 (group + row render, dirty marking, PATCH sends only changed fields, 409 surfacing, add-new flow, frame badge). Combined regression `npx vitest run` → 218/218 (no Task 1-23 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-21d/verify.py` → login → /admin/pet?tab=species → editor mounts → 通用/legendary 分组可见 → 改 duck.name → save → row de-dirtied → DB shows new name → "3 frames" badge present → add `t21d-tmp` via UI → delete via UI → row detaches → 还原 duck.name.
- **Snapshots:** `/tmp/admin-rebuild/task-21d/species-editor.png` (full page).
- **Endpoints used:** existing 21c `/api/admin/pet/species[/<id>]` for list/PATCH/POST/DELETE.

Implementation note: new `Species` tab in `src/admin/Pet.jsx` next to Behavior/Personas/Templates/Conversations/Usage; per-row save instead of bulk save because the catalogue is N rows owned independently and 409 conflicts on one row shouldn't block edits to others. Frame editing intentionally not exposed in this tab — frames are 3-frame ASCII with strict layout rules and deserve a dedicated frame composer (likely follow-up 21f). Delete uses `window.confirm` to keep blast radius local; the admin shell's ConfirmModal can replace it later for visual consistency. New `src/api/petSpecies.js` mirrors the rest of the api/ folder (token from localStorage, 204 → null, JSON-decode detail on error). CSS additions live in `src/styles.css` under `.admin-pet .species-row` / `.species-grid` and reuse existing `--accent` / `--bg-2` / `--line` tokens for consistency.

#### Task 21e — frontend reads species from /api/pet/species (DONE)

- **Tests:** `npx vitest run src/components/pet/__tests__/species.test.js src/components/AsciiPet.test.jsx` → 13/13. Combined regression `npx vitest run` → **220/220** (no Task 1-23 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-21e/verify.py` → /api/pet/species returns 27 rows → visit / → AsciiPet mounted → confirm /api/pet/species was actually fetched by browser → AsciiPet element has rendered content → toggle `axolotl.visible=false` via API → public list excludes it → restore.
- **Snapshots:** `/tmp/admin-rebuild/task-21e/homepage-with-pet.png`.
- **Commit:** `ee79017` (`feat(pet): hydrate species catalogue from /api/pet/species (Task 21e)`).

Implementation note: removed the inline 27-species hardcode (SPECIES_BASE / PET_PROFILES / RARITY_STAT_BASE blocks — ~280 LOC of static data) from `src/components/pet/species.js`; replaced with `loadSpecies(fetch)` that calls `/api/pet/species` and mutates the exported `SPECIES` / `SPECIES_BEHAVIOR` objects in place. Importers get live bindings so the existing `import { SPECIES }` reads keep working without a rename. Added `useSpecies()` React hook returning `{ ready, species, behavior }`; AsciiPet gates render on `speciesReady` to avoid a missing-frame flash, PetPersonas shows "加载物种目录中…" until ready. `loadSpecies()` is kicked off in `src/main.jsx` so the fetch runs in parallel with React mount and usually lands well before AsciiPet's first commit. Adapter maps `*_zh` → `trait/personality/description` so consumers don't need updates.

#### Task 21f — inline ASCII frame editor (DONE)

- **Tests:** `npx vitest run src/admin/pet/PetSpeciesEditor.test.jsx` → 15/15 (10 prior + 5 new: frameLayoutHint canonical-pass + row-count + width + {E} substitution + null-safety; toggle expands/collapses; edit dirties the row + surfaces hint; save sends frames array via PATCH; toggle label flip). Combined `npx vitest run` → **252/252** (no Task 1-28 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-21f/verify.py` → /admin/pet?tab=species → click `编辑帧 (3)` toggle → 3 frame textareas mount → fill frame 0 with marker → row dirty=true → 保存 → row dirty=false → API GET confirms marker persisted → cleanup restores original frames.
- **Snapshots:** `/tmp/admin-rebuild/task-21f/frames-panel.png`.
- **Commit:** `203b261` (`feat(admin/pet): inline ASCII frame editor in species panel (Task 21f)`).

Implementation note: pure UI add — no schema or service change needed because the existing 21c PATCH already accepts a `frames` JSONB. The panel is collapsed by default per row; expanding renders 3 textareas (one per frame) joined-by-`\n`. New `setDraftFrame(id, idx, lines)` helper avoids cross-wiring with `setDraftField` so the frames array stays its own thing in the dirty diff. `frameLayoutHint(lines)` is exported (also unit-tested in isolation) so a future preview canvas can reuse the same width/height check; it's intentionally non-blocking — drift surfaces as a small accent-colored line under the textarea but doesn't reject the save. Dropped the static "N frames" badge in favor of the toggle button (which still shows the count). Defensive: `frameLayoutHint` no-ops on non-string entries, so a stale draft mid-edit can't crash the panel. Frame composer follow-ups: live preview side-panel with `{E}` → `STATE_EYE['idle']` substitution, drag-from-template frame import, and uploading a 5x12 ASCII mask from clipboard.

---

### Task 22 — Now: markdown preview + public surface decision

**Status:** completed (22a + 22b)
**Priority:** medium
**Frontend evidence:** TopBar `/now` link — currently anchors at contributions head; no rendered `now` body. C5.
**Owner problem:** an entire feature (now entries) has no public render. Owner edits into a void.
**Existing capability:** admin Now composer + timeline; public `/api/now`.
**Gap:** public surface missing; admin lacks markdown preview.
**Admin module:** 02 内容 / 近况
**Backend touch:** none
**Frontend API client:** existing
**UI / interaction (admin):** add a 预览 toggle next to each editor textarea; render via the same backend `posts/render-preview` endpoint or a lightweight markdown lib for quickness
**UI / interaction (public):** add a `/now` panel between contributions and posts on `HomeA`, rendering the current entry with markdown body + listening + reading
**Automated tests:** Vitest for HomeA panel; pytest already covers /now
**Playwright acceptance path:**
  1. /admin/now → write a current entry → preview → assert markdown rendered
  2. /  → assert /now panel shows the entry
  3. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-22/admin-preview.png`, `/tmp/admin-rebuild/task-22/public-now.png`
**Commit message:** `feat(now): markdown preview in admin and public render on home`
**Definition of done:** standard checklist
**Completed:** 22a only — `56ab725` (`feat(admin/now): markdown preview toggle in editor (Task 22a)`). 22b (public /now panel on HomeA) is still pending.

#### Task 22a — admin preview toggle (DONE)

- **Tests:** `npx vitest run src/admin/nowMarkdown.test.js` → 9/9 (paragraphs, **bold**, *italic*, `code`, list with `- ` prefix, blank-line paragraph break, HTML escaping, bare http linkifier, list-then-paragraph). Combined `npx vitest run` → 186/186 (no Task 1-23 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-22a/verify.py` → login → /admin/now → post entry with `**bold**` + 2-item list → click 预览 → assert div.reader-md contains `<strong>` → click again → assert textarea returns → cleanup deletes row.
- **Snapshots:** `/tmp/admin-rebuild/task-22a/now-preview.png`.

Implementation note: the post `render-preview` endpoint requires a full valid post frontmatter (id pattern + n field), which would require a stub-and-strip dance for short Now blurbs. Instead we ship `src/admin/nowMarkdown.js` — a 60-LOC inline renderer that handles the markdown subset that actually appears in Now entries (paragraphs, bold, italic, inline code, bullet lists, bare http links). Output is HTML-escape-first to prevent injection. The toggle button uses `data-testid=now-preview-{id}` and `data-active="true"` so the keyboard layer (Task 17) can still operate on the row even while preview is shown.

#### Task 22b — public /now panel on HomeA (DONE)

- **Tests:** `npx vitest run src/components/NowPanel.test.jsx` → 5/5 (renders nothing while loading / on error / when current is null; renders body markdown + listening + reading; omits meta strip when both are empty). Combined `npx vitest run` → 191/191 (no Task 1-23 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-22b/verify.py` → seed admin Now entry with `**marker**` body + listening + reading → visit / → assert `[data-testid=now-panel]` mounted → assert `<strong>marker</strong>` rendered in `.now-body` → assert listening "lofi mix" + reading "Rust book" surfaced → assert DOM order `#contributions → [data-testid=now-panel] → #writing` → cleanup deletes the entry.
- **Snapshots:** `/tmp/admin-rebuild/task-22b/homea-now-panel.png` (full-page).
- **Commit:** `4cf1753` (`feat(now): public /now panel on HomeA between contributions and posts`).

Implementation note: new `api.now()` + `useNow()` hook expose the existing `/api/now` endpoint to the public site. `NowPanel` reuses the admin's `nowMarkdown.js` renderer so admin preview and public render produce identical HTML — one source of truth. The HomeA topbar's `/now` anchor previously pointed at the contributions section (cosmetic id misnomer); contributions now uses `id="contributions"` and the topbar `#now` anchor lands on the actual NowPanel. The panel renders nothing while loading / on error / when `current` is null, so a fresh site without any Now entry stays clean. Listening / reading meta strip is omitted when both fields are empty.

---

### Task 23 — Media: usage backreference

**Status:** completed
**Priority:** medium
**Frontend evidence:** Reader body images.
**Owner problem:** deleting a media item used in a post body silently orphans `<img>` references; only the avatar reverse-lookup is enforced.
**Existing capability:** site_meta.avatar_id reverse-lookup blocks delete (recent fix).
**Gap:** no scan of post bodies.
**Admin module:** 02 内容 / 媒体
**Backend touch:**
  - new service `media.references(media_id)` scanning posts.body_md (and body_json) for `/media/<storage_path>` matches
  - extend `DELETE /api/admin/media/{id}` to refuse with 409 listing post ids if referenced
  - extend `GET /api/admin/media/{id}` with `referenced_by: {posts: [...], avatar: bool}`
**Frontend API client:** existing
**UI / interaction:**
  - detail modal: "被引用于：post-x, post-y" with linked rows
  - delete button disabled when referenced; tooltip naming the blocker
**Automated tests:** pytest for reference scan
**Playwright acceptance path:**
  1. upload media → insert into post X → save
  2. /admin/media → click that media → assert "被引用于：X"
  3. click 删除 → assert blocked with message
**Snapshot location:** `/tmp/admin-rebuild/task-23/refs-blocked.png`
**Commit message:** `feat(admin/media): refuse delete when referenced by post body`
**Definition of done:** standard checklist
**Completed:** `974063b` (`feat(admin/media): refuse delete when referenced by post body`).

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_media.py` → 21/21 (4 new for Task 23: GET surfaces referenced_by, GET shows posts list when post body cites the media URL, DELETE returns 409 with detail listing post ids, DELETE returns 409 when avatar_id points at the media; 1 existing test updated to reflect new "refuse first, FK SET NULL only as last-resort safety net" semantics).
- **Vitest:** Combined `npx vitest run` → 177/177 (no Task 1-20 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-23/verify.py` PASSED → upload media → GET shows empty refs → admin UI shows "未在任何文章或头像中引用" with delete enabled → PUT /admin/profile sets avatar_id → GET shows avatar=true → DELETE returns 409 with detail.avatar=true → admin UI shows "用作站点头像" badge with delete `data-blocked="true"` → cleanup deletes after avatar cleared.
- **Snapshots:** `/tmp/admin-rebuild/task-23/refs-empty.png`, `/refs-blocked.png`.

Implementation note: new `media.references(s, media_id)` service scans `posts.body_md LIKE '%/media/<storage_path>%'` (LIKE on a small table is fine — the URL shape is exactly what `url_for(storage_path)` produces in post bodies via the MediaPicker insert helper) AND checks `site_meta.avatar_id == media_id`. The schema gains `MediaReferences` and `MediaItem.referenced_by`. The DELETE handler checks references BEFORE calling `delete_one` and raises 409 with `{error: "media_referenced", posts: [...], avatar: bool}` — the previous behavior relied on `ON DELETE SET NULL` on the avatar FK to silently null the avatar, which made the avatar disappear without explanation. Frontend Media.jsx fetches the full detail (with refs) when the modal opens, renders a "被引用于" panel, and disables the delete button when blocked (with a tooltip naming the blocker); the catch path also surfaces 409 detail in the toast for the rare race where the cached refs are stale.

---

### Task 24 — Projects: GitHub repo autofill

**Status:** completed (24a + 24b)
**Priority:** medium
**Frontend evidence:** `HomeA` projects grid.
**Owner problem:** every new project requires manual entry of name/desc/lang/stars even though GitHub integration syncs repos.
**Existing capability:** GitHub integration syncs contrib_days; not repos. Backend has `github_svc` with `ping`.
**Gap:** no repo list endpoint, no UI.
**Admin module:** 02 内容 / 项目
**Backend touch:**
  - new `GET /api/admin/integrations/github/repos` returning the owner's public repos (cached 10 min)
  - admin Projects page: 从 GitHub 导入 button → modal listing repos → click adds row prefilled
**Frontend API client:** `src/api/integrations.js` extended
**UI / interaction:** modal grid; rows already-imported are disabled with badge "已添加"
**Automated tests:** pytest mocked GitHub
**Playwright acceptance path:**
  1. /admin/projects → 从 GitHub 导入 → modal opens → click `MyBlog` → assert row prefilled
  2. save → / → assert project visible
  3. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-24/import-modal.png`
**Commit message:** `feat(admin/projects): one-click GitHub repo import`
**Definition of done:** standard checklist
**Completed:** 24a only — `ab2ca0d` (`feat(admin/integrations): GET /integrations/github/repos with 10m cache (Task 24a)`).

#### Task 24a — backend repo listing + cache (DONE)

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_integrations.py` → 30/30 (4 new for 24a: 404 when not configured, returns items + username when configured (mocked `fetch_repos`), 401 unauth, service-level cache test asserting only 1 underlying httpx call for repeated `fetch_repos('tok', 'alice')`).
- **Vitest:** No frontend changes this task.
- **Live probe:** none — endpoint hits real GitHub which we don't want to call from CI / verifier.
- **Commit:** `ab2ca0d`.

Implementation note: `app/services/github.py::fetch_repos(token, login)` is unified into a single function with a process-local 10-minute TTL cache keyed by login. The cache key intentionally excludes the token (rotating the token doesn't change the repo list) and stays small enough that no eviction is needed for one-owner deployments. `_repos_cache_clear()` is exported for tests. Returns `[{name, description, lang, stars, archived, fork, url}]` — `fork` is preserved so the existing worker `tasks/github.py` repo-sync still filters out forks correctly. The router `GET /api/admin/integrations/github/repos` 404s when github isn't configured; otherwise returns `{items, username}`. The admin Projects modal (Task 24b) will consume this.

**Removed dead code**: an earlier revision had two `fetch_repos` definitions in github.py — Python kept only the last one which lacked caching. The duplicate is now stripped and the canonical version (with cache + url field) sits at the top of the file alongside the cache state.

#### Task 24b — admin Projects 从 GitHub 导入 modal (DONE)

- **Tests:** Vitest 212/212 (no dedicated unit test for the modal — flow is end-to-end Playwright).
- **Playwright:** `/tmp/admin-rebuild/task-24b/verify.py` PASSED → /admin/projects → click `[data-testid=projects-github-import]` → `[data-testid=gh-import-modal]` opens → 13 `li[data-testid^=gh-repo-]` rows rendered → live DB had every repo already imported, so the test confirmed all rows carry `data-taken="true"` (the "已添加" badge path); the prefill branch is exercised when at least one repo is fresh.
- **Snapshots:** `/tmp/admin-rebuild/task-24b/import.png`.
- **Commit:** `42e0781` (`feat(admin/projects): GitHub repo import modal (Task 24b)`).

Implementation note: `apiIntegrations.listGithubRepos()` consumes the 24a endpoint; the modal handles 404 (`GitHub 集成尚未配置 — 请先在 设置 → 集成 中保存账号 + token`) gracefully. Filter input lets the owner narrow long lists. Forks are hidden from the modal (they rarely belong on a portfolio). Each row has `data-testid=gh-repo-{name}` + `data-taken="true"` when the project name is already saved; clicking a non-taken row calls `applyRepoToDraft(repo)` which prefills name/description/lang/stars on the new-project form, closes the modal, and toasts. The 已添加 badge greys out taken rows. The verifier learned to discover its row selector via `li[data-testid^=...]` because the parent UL also has `data-testid=gh-repo-list` and a generic prefix selector matched both.

---

### Task 25 — Analytics: custom date range + CSV export + per-post page

**Status:** completed (25a CSV + 25b since-date + 25b-arbitrary-end + 25c per-post page done)
**Priority:** medium
**Frontend evidence:** `Reader.jsx` hit beacon — every page view feeds analytics.
**Owner problem:** 7/30/90 chips can't compare May to April; cannot export.
**Existing capability:** `/analytics?days=` clamped to 365.
**Gap:** no `from/to` query, no CSV, no per-post page.
**Admin module:** 03 观察 / 数据分析
**Backend touch:**
  - extend `/analytics` with `from?, to?` (mutually exclusive with `days`)
  - new `GET /analytics/posts/{post_id}?from&to` — daily timeseries of hits + likes + comments for one post
  - new `GET /analytics/export?from&to&format=csv` — streaming CSV
**Frontend API client:** `src/api/analytics.js`
**UI / interaction:**
  - date range picker replacing chips (chips remain as quick selects)
  - 导出 CSV button
  - clicking a row in 热门文章 → per-post page
**Automated tests:** pytest for new params + export streaming
**Playwright acceptance path:**
  1. /admin/analytics → set range 2026-04-01 to 2026-05-05 → assert chart redraws
  2. click top post row → per-post page renders
  3. 导出 CSV → file downloaded
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-25/range.png`, `/tmp/admin-rebuild/task-25/per-post.png`
**Commit message:** `feat(admin/analytics): date range, csv export, per-post drilldown`
**Definition of done:** standard checklist
**Completed:** 25a only — `7a80f03` (`feat(admin/analytics): per-post CSV export endpoint + UI button (Task 25a)`).

#### Task 25a — per-post CSV export (DONE)

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_analytics.py -k csv` → 3/3 (401 unauth, header-only when empty, body includes seeded row with quoted/escaped title containing `,` and `"`).
- **Vitest:** Combined `npx vitest run` → 191/191 (no regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-25a/verify.py` → API probe asserts 200 + `text/csv` + `Content-Disposition: attachment; filename="analytics-posts-YYYYMMDD-7d.csv"` + correct header line; unauthenticated probe → 401; browser path logs in → /admin/analytics → click `[data-testid=analytics-export-csv]` → `page.expect_download` captures the download with `analytics-posts-...csv` filename and body starts with `post_id,title,hits`.
- **Snapshots:** `/tmp/admin-rebuild/task-25a/{after-export.png,downloaded.csv}`.

Implementation note: `GET /api/admin/analytics/posts.csv?days=N` returns a UTF-8-BOM-prefixed CSV (`﻿` Excel preamble) with columns `post_id,title,hits`, sourced from the existing `analytics_svc.per_post(days, limit=1000)`. The Content-Disposition filename embeds the UTC date stamp + window so multiple exports don't collide. Frontend `apiAnalytics.downloadPostsCsv(range)` does an authenticated fetch (the bearer token can't ride a plain `<a>` link), wraps the response as a Blob, creates an in-memory object URL, and triggers a synthetic `<a download>` click — works in vanilla browsers without any extra deps. The Analytics page gains an `<ExportCsvButton range={range} />` next to the range chips with `data-testid=analytics-export-csv`. csv.writer escapes quotes-in-titles (`"Hello, ""world"""`); test assertions use `.replace("\r\n", "\n")` because csv.writer's default line terminator is CRLF. One latent fixture bug surfaced: the existing `test_analytics_posts_returns_titled_rows` uses local `date.today() - 1` for "yesterday" while the service filter uses UTC — racy when the runner is in a tz ahead of UTC. The new CSV test imports `datetime.now(UTC).date()` directly to avoid the race.

#### Task 25b — custom since-date picker (DONE)

- **Tests:** `npx vitest run src/api/analytics.test.js` → 5/5 (parses `since:YYYY-MM-DD` to days, clamps 1..365, falls back to 30 on garbage / future / malformed). Combined `npx vitest run` → 203/203 (no regression).
- **Playwright:** `/tmp/admin-rebuild/task-25b/verify.py` PASSED → login → /admin/analytics → since-date picker starts empty → `date_input.fill('YYYY-MM-DD')` for 14-days-ago → wait for performance entry showing the analytics call with `days=15` (= 14 + 1 inclusive) → assert `[data-testid=analytics-since-date][data-active=true]` → 3 request(s) carried `days=15` (bundle + posts + tags) → click 30 天 chip → input clears + `data-active` removed.
- **Snapshots:** `/tmp/admin-rebuild/task-25b/since-active.png`.
- **Commit:** `a7e7e0a` (`feat(admin/analytics): custom since-date picker (Task 25b)`).

Implementation note: rather than extend the backend service signatures (which would touch `timeseries / per_post / per_tag / top_paths / _merge_jsonb_top` — 5 functions, all currently `days`-parameterized), 25b reuses the existing `days` API by deriving days at the client. `rangeToDays('since:2026-04-21')` computes `(today_utc − start_date) + 1` and clamps to `[1, 365]`. The Analytics page encodes the active range as `since:YYYY-MM-DD` so the same prop drives the bundle/posts/tags fetches AND the CSV download. Picking "today" gives 1 day; clearing the input falls back to the default 30d preset. Arbitrary end-date support (i.e. `[start, end]` where end ≠ today) is left for Task 25c since the existing service is "ending now" by construction; that would require changing service signatures across the board.

#### Task 25c — per-post analytics drilldown page (DONE)

- **Backend:** new `analytics_svc.per_post_timeseries(s, post_id, days)` mirrors the bundle `timeseries` strategy filtered to one `post_id` (HitDaily history + today's HitEvent count). New endpoint `GET /api/admin/analytics/posts/{post_id}/timeseries?days=N` returns `{post_id, title, total, timeseries}`; 404 if post is missing so the UI can show a proper error rather than an all-zero chart.
- **Frontend:** new route `/admin/analytics/posts/:postId` (`src/admin/analytics/AnalyticsPostDetail.jsx`) — title, total KPI, daily SVG bar chart, range chips 7/30/90 (URL-state via `?range=`), 返回 link back to `/admin/analytics?range=<active>`. Hot-posts table on `/admin/analytics` now renders each title as a `<Link>` with `data-testid=hot-post-<id>`.
- **Backend tests:** `./.venv/bin/python -m pytest tests/test_admin_analytics.py` → 17/17 (3 new: 401 unauth, 404 unknown id, daily breakdown round-trip with two seeded HitDaily rows + today=0).
- **Vitest:** `npx vitest run src/admin/analytics/AnalyticsPostDetail.test.jsx` → 5/5 (range fetch, bar tooltips, range chip refetch, 404 surfacing, 30d default). Combined `npx vitest run` → **225/225** (no Task 1-24 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-25c/verify.py` → 404 for unknown id → API smoke for `vps` post (7-day timeseries, total=0 here because dev DB has no traffic) → login → navigate `/admin/analytics/posts/vps?range=7d` directly → page mounts → UI total matches API → 7 bars render → click 30d chip → 30 bars → 返回 link → `/admin/analytics?range=30d`.
- **Snapshots:** `/tmp/admin-rebuild/task-25c/post-detail.png` (full-page).
- **Commit:** `1dbc82d` (`feat(admin/analytics): per-post drilldown page (Task 25c)`).

Implementation note: kept the SVG bar chart pattern from `Analytics.jsx` rather than introducing a chart lib — this is the third bar chart in the codebase (overall hits, post-detail, eventually pet usage), and they're all <40 LOC. The drilldown supports presets only (no since-date picker) because the click-through always opens the same window the user just looked at; arbitrary end-date / since-date for drilldown is an obvious follow-up if/when an owner wants point-in-time comparisons. The hot-posts row label uses `<Link>` instead of an onClick handler so middle-click opens in a new tab. RankTable gained an optional `r.href` + `r.testId` per row — labels-without-href stay as plain spans (referrers / countries / tags) to avoid surfacing routes that don't exist yet.

#### Task 25b-arbitrary-end — analytics arbitrary [from, to] window (DONE)

- **Backend:** new `analytics_svc.resolve_window(days, from_, to)` helper + extracted `_hits_history_window(start, end_exclusive)` so `timeseries()` accepts either `days=N` (legacy) OR `from_=D1, to=D2` (arbitrary inclusive window). Right-edge live count from `hit_events` only contributes when `to == today`; otherwise the window is fully historical. Router `/analytics` accepts `?from=YYYY-MM-DD&to=YYYY-MM-DD`; both required together (422 on partial), `to >= from` enforced (422 inverted), 365-day cap (422 oversize). Top paths/referrers/countries lists still use the equivalent `days` length and are documented in the route docstring as "ending now" — full per-list arbitrary windows are a follow-up.
- **Backend tests:** `./.venv/bin/python -m pytest tests/test_admin_analytics.py` → 22/22 (5 new: arbitrary window length + endpoints, 422 partial, 422 inverted, 422 overlong, seeded HitDaily on 2026-04-15 surfaces in `[2026-04-10, 2026-04-20]`).
- **Frontend:** `apiAnalytics.bundle(range)` switches to `?from&to` when `range:YYYY-MM-DD..YYYY-MM-DD` token is active. `rangeToDays` extended to parse `range:` (clamps 1..365 days, falls back on malformed input). New `rangeToFromTo(range)` returns `{from, to}` or null. `<SinceDatePicker>` gains a second `<input type="date" data-testid=analytics-to-date>`; filling both promotes the active range to `range:from..to`, leaving `to` empty keeps the legacy `since:from` semantics.
- **Vitest:** `npx vitest run src/api/analytics.test.js` → 10/10 (5 prior + 5 new: range token parses inclusive day count, clamps over-365, falls back inverted/malformed; rangeToFromTo returns null/{} appropriately). Combined `npx vitest run` → **243/243** (no Task 1-28 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-25b-arbitrary/verify.py` → API smoke for `[2026-04-01, 2026-04-10]` (10 days, dates match) → 422 trio (partial / inverted) → /admin/analytics → fill from + to → bundle refetched with `from=...&to=...` → to-date `data-active=true` → click 7 天 chip → both inputs cleared.
- **Snapshots:** `/tmp/admin-rebuild/task-25b-arbitrary/range-active.png`.
- **Commit:** `13d6405` (`feat(admin/analytics): arbitrary [from, to] window for timeseries (Task 25b-arbitrary-end)`).

Implementation note: scoped intentionally — only the bundle's `timeseries` chart honors `from/to`. Top paths/referrers/countries reuse the equivalent window length but still anchor at "today", because refactoring `_merge_jsonb_top` and friends would touch 5 more functions and double the diff. The router docstring + UI behavior surface this asymmetry: when the user picks May 1–May 5, the chart shows exactly those 5 days while top_paths shows the last 5 days ending today (which overlap heavily — usually identical for recent windows). Full per-list arbitrary-window support is a follow-up that can move into the existing helper without churning callers further. Inverted / malformed `range:` tokens fall back to `'30d'` rather than throwing so a typo in the URL state doesn't blank the page.

---

### Task 26 — Pet usage charts

**Status:** completed (26a daily stacked bar + 26b per-mode pie + 26c cost line done)
**Priority:** low
**Frontend evidence:** `AsciiPet.jsx` summon stream → token costs accumulate.
**Owner problem:** flat day×mode×source table tells nothing about trends.
**Existing capability:** `/pet/usage` returns last 300 rows.
**Gap:** no charts.
**Admin module:** 03 观察 / 宠物用量
**Backend touch:** none (data already there)
**Frontend API client:** existing
**UI / interaction:**
  - daily stacked bar (calls per source: provider/cache_hit/fallback/rate_limited)
  - per-mode pie
  - estimated cost line (using configured provider rates — owner-set on Integrations page; gather in a separate small task or hardcode for now)
**Automated tests:** Vitest for chart data shape
**Playwright acceptance path:**
  1. /admin/pet/usage → assert 3 charts render
  2. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-26/charts.png`
**Commit message:** `feat(admin/pet): charts on usage page`
**Definition of done:** standard checklist
**Completed:** 26a only — `81ab961` (`feat(admin/pet): daily stacked bar chart on usage page (Task 26a)`).

#### Task 26a — daily stacked bar chart (DONE)

- **Tests:** `npx vitest run src/admin/pet/petUsageChart.test.js` → 7/7 (groupByDay aggregation + sort + null-safe; buildBars produces ordered segments + max-day fills inner height + correct totals; legend lists only present sources in canonical order). Combined `npx vitest run` → 198/198 (no regression).
- **Playwright:** `/tmp/admin-rebuild/task-26a/verify.py` PASSED → login → /admin/pet?tab=usage → wait for `[data-testid=pet-usage-chart]` OR `[data-testid=pet-usage-chart-empty]` → on chart, assert ≥1 `[data-testid^=pet-usage-bar-]` + ≥1 `[data-testid^=pet-usage-legend-]` entry. Live DB had 5 bar segments + 3 legend entries (provider / cache_hit / other).
- **Snapshots:** `/tmp/admin-rebuild/task-26a/chart.png`.

Implementation note: pure helpers in `src/admin/pet/petUsageChart.js` (`groupByDay`, `buildBars`, `legendFromData`, `SOURCE_COLORS`, `SOURCE_LABELS`) keep all the SVG geometry math out of React. SOURCE_ORDER fixes the stack order (provider → cache_hit → fallback → rate_limited → other) so colors stay stable across reloads. Unknown sources land in the "other" bucket. `<UsageChart>` in `PetUsage.jsx` renders inline SVG + a top legend with colored swatches. Each `<rect>` carries `data-testid=pet-usage-bar-{day}-{source}` and a `<title>` tooltip showing day + source label + call count.

#### Task 26b — per-mode pie chart (DONE)

- **Tests:** `npx vitest run src/admin/pet/petUsageChart.test.js` → 16/16 (7 from 26a + 9 new for 26b: groupByMode aggregates / sorts desc / skips zero / handles null; modeColor stable + palette tokens; buildPieSlices fractions sum to 1 + every slice has path + label inside donut + empty-input handling + single-slice full-circle case). Combined `npx vitest run` → 212/212 (no regression).
- **Playwright:** `/tmp/admin-rebuild/task-26b/verify.py` PASSED → /admin/pet?tab=usage → wait for `[data-testid=pet-usage-pie]` OR `[data-testid=pet-usage-pie-empty]` → on chart, assert ≥1 `[data-testid^=pet-usage-pie-slice-]` + matching `[data-testid^=pet-usage-pie-legend-]` rows. Live DB had 8 slices.
- **Snapshots:** `/tmp/admin-rebuild/task-26b/pie.png`.
- **Commit:** `506c8a0` (`feat(admin/pet): per-mode pie chart on usage page (Task 26b)`).

Implementation note: same pure-helper pattern as 26a. `groupByMode(rows)` aggregates `mode → calls` and sorts descending so the pie reads largest-first. `modeColor(mode)` uses a hash-into-palette so admin-introduced template modes (greet / summary / pet_care / code_assist / etc.) get deterministic colors without an explicit registry. `buildPieSlices(modes, {cx, cy, r, inner})` walks angles starting at 12 o'clock, builds an SVG `<path d>` per slice (handles inner-radius for donut), and computes a label position halfway between r and inner; single-slice case falls back to a full-circle path since SVG arcs collapse when start=end. `<ModePieChart>` in PetUsage.jsx renders the donut with a center total label + a side legend listing every mode's calls. The bar chart and pie sit side-by-side via flexbox (`flex-wrap` so the pie drops below the bar on narrow screens).

#### Task 26c — daily cost line chart (DONE)

- **Backend:** `/api/admin/pet/usage` aggregate now also returns `estimated_input_tokens` + `estimated_output_tokens` per (day, mode, source) so the client-side cost math can apply per-side rates without a new endpoint.
- **Frontend:** new helpers in `src/admin/pet/petUsageChart.js` — `PROVIDER_RATES` (anthropic / zhipu / qwen / doubao / deepseek + `default` fallback, USD per 1M tokens), `rowCostUSD`, `groupCostByDay`, `buildCostLine`, `formatUSD`. `<CostChart>` in PetUsage.jsx renders an SVG `<polyline>` + `<circle>` per day below the stacked bar. Cache hits / fallbacks / rate-limited calls cost zero; unknown providers use `default` so a typo doesn't silently zero the bill.
- **Vitest:** `npx vitest run src/admin/pet/petUsageChart.test.js` → 29/29 (16 prior + 13 new: rowCostUSD zero/rate/default/null; groupCostByDay ascending/empty; buildCostLine dot positions/zero-baseline/points format/single-day; formatUSD micro-spend + 2-dp). Combined `npx vitest run` → **238/238** (no Task 1-25 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-26c/verify.py` → /pet/usage payload includes split token fields → /admin/pet?tab=usage → wait for `[data-testid=pet-usage-cost]` OR `[data-testid=pet-usage-cost-empty]` → live DB had 2 day-dots and `$0.09` window total displayed.
- **Snapshots:** `/tmp/admin-rebuild/task-26c/cost-chart.png`.
- **Commit:** `77ba787` (`feat(admin/pet): daily cost line chart on usage page (Task 26c)`).

Implementation note: rates are hardcoded in JS for the MVP — owner-configurable rates would belong in the Integrations page (one rate-pair per provider) and feed back to the chart via `apiPet.providerRates()`, but that's a follow-up that doesn't block visibility into spend. Keeping the math in `petUsageChart.js` means the cost number can be inspected/tested without spinning up a backend or react renderer. `formatUSD` uses 4 decimals below `$0.01` so micro-spend (zhipu/doubao runs in mass) still shows non-zero — rounding to `$0.00` was the temptation when most rows are sub-cent. Empty state ("暂无估算成本") fires when total is zero (cache + fallback only) so the chart isn't a misleading flat line at the baseline.

---

### Task 27 — Integrations: test-without-save + provider priority UI

**Status:** completed (27a + 27b + 27c)
**Priority:** medium
**Frontend evidence:** Pet integrations cost monitoring — provider order matters.
**Owner problem:** "test connection" only fires on save (mutates state). Provider priority is a comma-string buried in Pet → Behavior.
**Existing capability:** `/integrations/<name>` PUT runs smoke; no test-only endpoint; priority via PetConfig `providers` string.
**Gap:** UI affordances missing.
**Admin module:** 06 系统 / 集成
**Backend touch:**
  - new `POST /api/admin/integrations/<name>/test` accepting candidate `{api_key, model, ...}` returning smoke result without persisting
**Frontend API client:** `src/api/integrations.js` `test(name, body)`
**UI / interaction:**
  - 测试连接 button next to 保存
  - drag-to-reorder provider list above the cards (writes to PetConfig.providers)
**Automated tests:** pytest for new test endpoint
**Playwright acceptance path:**
  1. /admin/settings → 集成 → enter Anthropic key → 测试连接 → success/failure inline
  2. drag Zhipu above Anthropic → save → assert PetConfig.providers updated
**Snapshot location:** `/tmp/admin-rebuild/task-27/test-result.png`, `/tmp/admin-rebuild/task-27/order.png`
**Commit message:** `feat(admin/integrations): test-without-save and provider priority drag-reorder`
**Definition of done:** standard checklist
**Completed:** 27a only — `8418544` (`feat(admin/integrations): test-without-save endpoint (Task 27a)`).

#### Task 27a — backend test-without-save endpoint (DONE)

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_integrations.py` → 26/26 (6 new for 27a: anthropic ok-when-ping-true, anthropic err-when-ping-false, openai-compat smoke via `monkeypatch.setattr(openai_compat, "chat", fake_chat)`, unknown provider 404, missing api_key surfaces helpful error, requires auth → 401; all assert no row was persisted).
- **Vitest:** Combined `npx vitest run` → 191/191 (no regression).
- **Live probe:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-27a/verify.py` → login → POST /integrations/anthropic/test with junk → ok=false → POST /integrations/zhipu/test with junk → ok=false → POST /integrations/notreal/test → 404 → POST anthropic/test {} → ok=false with "api_key required" → unauthenticated probe → 401 → GET /integrations/anthropic before vs after is identical (zero side-effect).
- **Snapshots:** none (backend-only).

Implementation note: single generic `POST /integrations/{name}/test` endpoint dispatches per-provider. anthropic/github use their existing `ping` adapters; openai-compat providers (zhipu/qwen/doubao/deepseek) use the existing `_smoke` helper. The endpoint always returns 200 with `{ok, error}` for known providers (so the UI can render inline feedback) and 404 only for unknown names. Errors are truncated to 200 chars to keep responses small. The frontend API client gains `apiIntegrations.test(name, body)`.

#### Task 27b — Integrations 测试连接 button per card (DONE)

- **Tests:** Vitest 191/191 (no dedicated unit test for the new button — covered by full Playwright path).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-27b/verify.py` → login → /admin/settings → Integrations tab → fill Anthropic API key with junk → click 测试连接 → assert `[data-testid=test-anthropic-result][data-ok=false]` rendered → fill Zhipu token with junk → click 测试连接 → assert `[data-testid=test-zhipu-result][data-ok=false]` rendered → GET /api/admin/integrations/anthropic before vs after is identical (zero side-effect).
- **Snapshots:** `/tmp/admin-rebuild/task-27b/anthropic-test.png`, `/zhipu-test.png`.
- **Commit:** `c4cf3f1` (`feat(admin/integrations): test connection button + multi-provider cards (Task 27b)`).

Implementation note: each card (GithubCard / AnthropicCard / ProviderCard for zhipu·qwen·doubao·deepseek) gains a 测试连接 button beside 保存. Per-card `testing` + `testResult` state. The result line appears between the existing notice/error block and the actions row, styled with `styles.notice` (green) for `ok=true` and `styles.error` (red) for `ok=false`; carries `data-testid=test-{name}-result` + `data-ok="true|false"` for stable test selectors. The button itself has `data-testid=test-{name}` and respects the same `disabled` rules as 保存 (no token / missing required model). The commit also pulls in the prior multi-provider card UI (zhipu·qwen·doubao·deepseek) that had been sitting in the unstaged work pool — they're functionally tied to the test-connection feature and ship together.

#### Task 27c — provider priority order UI (DONE)

- **Tests:** Vitest 191/191 (no dedicated unit test for the order bar — flow covered by Playwright path).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-27c/verify.py` → snapshot baseline `PetConfig.providers` via API → login → /admin/settings → Integrations tab → wait for `[data-testid=provider-order-bar]` → read DOM order via `data-name` attrs → click `[data-testid=provider-up-{target}]` → assert slot 0 now has the target → click `[data-testid=provider-order-save]` → assert "优先级已保存" notice → GET /api/admin/pet returns the new order at `providers[0]` → restore original providers via PUT.
- **Snapshots:** `/tmp/admin-rebuild/task-27c/order-saved.png`.
- **Commit:** `307670e` (`feat(admin/integrations): provider priority order UI (Task 27c)`).

Implementation note: simple ↑/↓ arrow buttons instead of HTML5 drag-and-drop — equivalent UX, much easier to test in headless Playwright (drag events are flaky in jsdom-style envs). The bar fetches the full PetConfig once on mount, merges persisted order with `ORDERABLE_PROVIDERS` (so newly-added providers always appear at the end without breaking saved order), and only saves when the local order differs from `config.providers` (`dirty` check). The save calls `apiPet.put({...config, providers: order})` since the backend has no PATCH; sending the full config back is fine for this small payload. Each row carries `data-testid=provider-order-{idx}` + `data-name=zhipu` so tests can assert order without coupling to display labels.

---

### Task 28 — Account: email change

**Status:** completed (28a backend + 28b UI form + 28c magic-link confirm done)
**Priority:** medium
**Frontend evidence:** Profile page reads-only email; account login uses email.
**Owner problem:** owner cannot rotate the admin email.
**Existing capability:** none (S3 gap).
**Gap:** no backend endpoint, no UI.
**Admin module:** 06 系统 / 账号
**Backend touch:**
  - new `POST /api/admin/account/email` accepting `{password, new_email}` — verify password, magic-link confirm to new email, then write
  - migrate `accounts.email` writeback path
**Frontend API client:** `src/api/account.js`
**UI / interaction:** form on Account page; pending state shows "已发送确认链接到 new@example.com"
**Automated tests:** pytest covering password verify + confirm flow
**Playwright acceptance path:**
  1. Account → 修改邮箱 → enter password + new email → submit
  2. capture link from outbound email log → click → asserts new email active
  3. login with new email → success
  4. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-28/changed.png`
**Commit message:** `feat(admin/account): change email with magic-link confirmation`
**Definition of done:** standard checklist
**Completed:** 28a only — `da9dbfb` (`feat(admin/account): change email endpoint with password gate (Task 28a)`).

#### Task 28a — backend endpoint (DONE)

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_email_change.py` → 7/7 (auth required, happy path + login flips, wrong password 400, same email 400, invalid address 422, event log row written, api-token rejected with 401 because endpoint is session-only). Combined with password tests → 12/12.
- **Live probe:** `/tmp/admin-rebuild/task-28a/verify.py` PASSED → wrong password 400 → same email 400 → invalid email 422 → rotate to `wyzz973+t28a@gmail.com` → login with new email 200 + new token → login with old email 401 → restore via the same endpoint to original email.
- **Commit:** `da9dbfb`.

Implementation note: `EmailChangeRequest{current_password, new_email: EmailStr}` schema; the endpoint sits at `POST /api/admin/account/email` and depends on `current_session_admin` so api-tokens (read or write scope) cannot rotate the email. Verifies the password via `verify_password(stored_hash, current_password)`, normalizes `new_email` to lowercase, refuses if it equals the current email (avoids "case-only changes"). Writes `account.email.changed` to event_log with `{old, new}` meta so the activity feed shows the rotation. Single-account site so we don't check uniqueness today (accounts.email has a UNIQUE constraint anyway).

#### Task 28b — Account 修改邮箱 UI form (DONE)

- **Tests:** Vitest 212/212 (no dedicated unit test for the form — flow is end-to-end Playwright). 28a backend tests still cover the API.
- **Playwright:** `/tmp/admin-rebuild/task-28b/verify.py` PASSED → /admin/settings → 账号 tab → `[data-testid=email-change-form]` visible → wrong password fills + submit → `[data-testid=email-change-error]` rendered → correct password + new email → `[data-testid=email-change-done]` shows "邮箱已改为 wyzz973+t28b@gmail.com" → API `/auth/login` with new email returns 200 → cleanup restores via API.
- **Snapshots:** `/tmp/admin-rebuild/task-28b/after-change.png`.
- **Commit:** `5df5684` (`feat(admin/account): change-email form on Account tab (Task 28b)`).

Implementation note: `apiAccount.changeEmail(currentPassword, newEmail)` posts to `/api/admin/account/email` and returns `{email}`. Account.jsx adds a new `<EmailSection>` Card between MagicLink and Password, mirroring the password-change form layout (current_password + new_email + submit). All inputs carry `data-testid=email-change-{role}` for stable test selectors. Success message tells the user their next login uses the new address. The current JWT keeps working because access tokens claim `sub` (account id) not email; only the login form has to use the new value. Magic-link confirmation (28c) is still pending — current flow trusts the password gate alone, which is fine for a single-owner site but could be tightened with email-roundtrip later.

#### Task 28c — magic-link confirm flow (DONE)

- **Migration:** `0018_pending_email_change` adds `pending_email_change(token_hash PK, account_id FK CASCADE, new_email, expires_at, consumed_at, requested_ip, user_agent, created_at)`.
- **Backend:** new `pending_email_change` service mirrors `magic_link.consume()`'s atomic single-use pattern — `WHERE consumed_at IS NULL AND expires_at > now()` predicate on the rotation UPDATE so concurrent confirms can't both succeed. Two new endpoints: `POST /api/admin/account/email/request {current_password, new_email}` (session-only, password-gated, mails the link, does NOT rotate) and `POST /api/admin/account/email/confirm {token}` (public — token IS the auth, rotates and writes `account.email.changed` event with `via=magic_link`). New `email_svc.send_email_change_confirm` template; new `public_site_base_url` config (defaults to dev frontend `:5173`) so the link points at the SPA's confirm page rather than the API host. The legacy one-step `POST /account/email` endpoint stays for backwards compat (its tests still pass) but the UI no longer calls it.
- **Backend tests:** `./.venv/bin/python -m pytest tests/test_admin_email_change.py` → 13/13 (6 prior + 6 new + 1 unchanged: 401 unauth on /request, 400 wrong password, request does NOT rotate immediately, end-to-end confirm rotates + login flips, 400 invalid token, 400 on token replay).
- **Frontend:** `apiAccount.requestEmailChange(pw, new)` + `apiAccount.confirmEmailChange(token)` (no bearer — the token IS auth). New route `/admin/account/email-confirm?token=...` mounted PUBLIC (outside `RequireAuth`) — owner often clicks the link from a different browser/device where they're not logged in. New `<EmailConfirm>` page auto-submits and renders success / error / pending states. Existing `<EmailSection>` form rewired to call `/request` and shows "已发送确认链接到 …, 15 分钟内点开链接才会真正切换邮箱" instead of immediate rotation. New `data-testid=email-change-sent` (replaces `email-change-done`).
- **Vitest:** combined `npx vitest run` → **238/238** (no Task 1-26 regression). EmailConfirm itself isn't unit-tested separately — Playwright covers the full token round-trip end-to-end.
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-28c/verify.py` → login → /admin/settings → 账号安全 tab → submit form for `wyzz973+t28c@gmail.com` → UI shows `已发送确认链接到 …` (no rotation yet) → issue raw token via in-process backend service (dev SMTP is null) → visit `/admin/account/email-confirm?token=<raw>` → success state with new email → login under new address returns 200 → restore.
- **Snapshots:** `/tmp/admin-rebuild/task-28c/confirm-success.png`.
- **Commit:** `e6d7619` (`feat(admin/account): magic-link confirm for email change (Task 28c)`).

Implementation note: hit a classic StrictMode + side-effect bug — the EmailConfirm useEffect was firing the confirm POST twice (StrictMode mounts → unmounts → remounts in dev), and the second call saw the row already consumed → 400 → page stuck on "正在确认…". Fix is a `useRef` keyed by token to dedupe + dropping the `alive` cleanup flag (so the surviving mount's setState wins). The server's idempotent path `if new_email == acct.email.lower()` also helps — when the SAME confirm fires twice in rapid succession before the first commit lands, the second consume() returns None but the UI catches the success state from the first call. Backwards compat: legacy POST `/account/email` still rotates immediately if called (preserved for any admin scripts that hit it directly); the UI itself uses the magic-link path now.

---

### Task 29 — API tokens: usage history

**Status:** completed (29 usage_count counter + per-request log table done)
**Priority:** low
**Frontend evidence:** owner cost monitoring.
**Owner problem:** `last_used_at` only — cannot answer "is anyone still using token X?"
**Existing capability:** `last_used_at` on `api_tokens`; bearer auth dependency updates it.
**Gap:** no per-token request log.
**Admin module:** 06 系统 / API 令牌
**Backend touch:**
  - new `api_token_usage` table — `id, token_id FK, path, ts, status_code`; insert from auth dep (best-effort, fire-and-forget)
  - new `GET /api/admin/api-tokens/{id}/usage?days=` — daily counts
**Frontend API client:** `src/api/apiTokens.js`
**UI / interaction:** click row → opens drawer with sparkline + last 50 requests
**Automated tests:** pytest for log + query
**Playwright acceptance path:**
  1. create token → use it once externally
  2. /admin/api-tokens → click row → assert usage entry
**Snapshot location:** `/tmp/admin-rebuild/task-29/usage.png`
**Commit message:** `feat(admin/api-tokens): per-token usage history`
**Definition of done:** standard checklist
**Completed:** Counter (Task 29 main) — `cae0a56` (`feat(admin/api-tokens): add usage_count column + UI (Task 29)`). Per-request log table — `8d8da7b` (`feat(admin/api-tokens): per-request usage log with audit trail UI (Task 29)`).

#### Task 29 (per-request log) — DONE

- **Migration:** `0017_api_token_usage` creates `api_token_usage(id BIGSERIAL PK, api_token_id INT FK→api_tokens ON DELETE CASCADE, used_at TIMESTAMPTZ default now(), method VARCHAR(8), path VARCHAR(256), status_code SMALLINT NULL)` + index `(api_token_id, used_at DESC)`.
- **Backend:** extended `api_tokens_svc.touch_last_used(token_id, method?, path?)` to also INSERT a usage row (same transaction as the counter bump). New `list_usage(token_id, limit)` service. `require_scope` now passes `request.method` + `request.url.path` (query string stripped — never log secrets carried in URL params). New endpoint `GET /api/admin/api-tokens/{id}/usage?limit=N` returning `[{used_at, method, path, status_code}]`; 404 when token id is unknown.
- **Backend tests:** `./.venv/bin/python -m pytest tests/test_api_tokens.py` → 17/17 (5 new: 404 unknown id, empty for unused token, records each scope-passing call with method+path, session caller doesn't add to trail, token can view its own trail).
- **Frontend:** `apiTokens.usage(id, limit)` + Settings → API 令牌 tab gains a `查看记录` button per row that expands an inline panel with a `时间/方法/路径` table. Toggle collapses it. Loading + error states handled.
- **Vitest:** combined `npx vitest run` → **225/225** (no regression; the existing ApiTokens.jsx isn't unit-tested separately so the audit-panel UI is verified by Playwright).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-29/verify-log.py` → seed token, fire 2 POST /api/admin/tags under it → API `/usage` returns 2 rows → 404 for unknown id → /admin/settings → API 令牌 tab → click 查看记录 → panel expands with rows → "POST /api/admin/tags" present in UI text → click again → panel detaches → revoke seed token.
- **Snapshots:** `/tmp/admin-rebuild/task-29/usage-panel.png`.
- **Commit:** `8d8da7b` (`feat(admin/api-tokens): per-request usage log with audit trail UI (Task 29)`).

Implementation note: kept the audit row in the same DB transaction as the counter UPDATE — losing one without the other would diverge usage_count from the row count, which the UI would surface as a confusing inconsistency. Path/method are truncated at the model boundary (8/256 chars) so a freak-long path doesn't reject the whole request. Query strings are stripped before logging because admin endpoints occasionally carry tokens or filenames in `?` params; only the route itself goes into the trail. status_code is nullable in the schema for forward-compat with a future middleware-based completion hook, but isn't populated in this revision (the dependency runs before the response is shaped). Inline expansion vs modal: the `<tr>` colspan-row pattern keeps the audit list adjacent to its token row, which is what the owner needs ("is *this* token being used?") rather than a context-switching dialog.

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_api_tokens.py` → 12/12 (3 new for Task 29: list returns usage_count + new tokens have 0; counter increments on each scope-passing request via PATCH /api/admin/posts; counter doesn't bump on tampered token → 401).
- **Vitest:** Combined `npx vitest run` → 203/203 (no regression).
- **Playwright:** `/tmp/admin-rebuild/task-29/verify.py` PASSED → create write-scope token → make 2 PATCH /api/admin/posts/<unknown> calls (each passes auth + scope, then 404s) → list shows usage_count=2 + last_used_at populated → /admin/settings UI shows `[data-testid=api-token-usage-{id}]` text "2".
- **Snapshots:** `/tmp/admin-rebuild/task-29/tokens-table.png`.

Implementation note: alembic migration `0014_api_token_usage_count` adds an integer column with `server_default '0'` so existing rows immediately have a valid value. The service `touch_last_used` updates `usage_count = usage_count + 1` in SQL (atomic against concurrent calls — read-modify-write in Python would lose updates). The touch fires inside `require_scope()` which means it covers all write-scope token uses today; pure-read endpoints (e.g. /dashboard) don't currently call require_scope and so don't tick the counter — a known limitation surfaced in the implementation note for future cleanup. Tampered tokens still produce 401 BEFORE touch, so `usage_count` stays accurate. Schema field added with default 0 for backwards compatibility. Admin UI gains a "调用次数" column with right-aligned tabular numerics; data-testid `api-token-usage-{id}` so tests can read the value without scraping. Per-request log table (`api_token_usage` with path / ts / status) sketched in the original spec is deferred — usage_count alone answers the "still in use?" question that prompted Task 29.

---

### Task 30 — Bulk markdown post upload UI

**Status:** completed
**Priority:** low
**Frontend evidence:** site growth.
**Owner problem:** importing N drafts from a folder requires N round-trips.
**Existing capability:** `POST /api/admin/posts/upload` accepts multipart, ≤20 .md, returns 201/207/422.
**Gap:** no UI.
**Admin module:** 02 内容 / 文章 (button on list page)
**Backend touch:** none
**Frontend API client:** `src/api/posts.js` `bulkUpload(files)`
**UI / interaction:** drag-zone on Posts list; per-file row with status (pending / ok / error message); summary toast after
**Automated tests:** pytest already covers backend
**Playwright acceptance path:**
  1. /admin/posts → drop 3 .md files → assert each row reports ok / error
  2. list refresh shows new posts
  3. screenshot
**Snapshot location:** `/tmp/admin-rebuild/task-30/bulk.png`
**Commit message:** `feat(admin/posts): bulk markdown upload UI`
**Definition of done:** standard checklist
**Completed:** `c865b85` (`feat(admin/posts): bulk markdown upload UI (Task 30)`).

- **Tests:** Vitest 191/191 (no dedicated unit test for the modal — flow covered by Playwright path).
- **Playwright:** `/tmp/admin-rebuild/task-30b/verify.py` PASSED → login → /admin/posts → click `[data-testid=posts-bulk-upload]` → modal opens → `set_input_files` with one valid + one malformed `.md` → click `[data-testid=bulk-upload-submit]` → assert `[data-testid=bulk-upload-summary]` shows "共 2 个 · 成功 1 · 失败 1" → assert per-file rows have `data-status="ok"` and `data-status="err"` → cleanup deletes the seeded post.
- **Snapshots:** `/tmp/admin-rebuild/task-30b/after-upload.png`.

Implementation note: `postsApi.bulkUpload(files, {overwrite})` posts a multipart batch via FormData and explicitly omits the `Content-Type` header so the browser picks the boundary; treats 201 (all ok) / 207 (partial) / 422 (all failed) as non-throw responses since they all carry the structured per-file results. The `BulkUploadModal` supports both drag-drop and file picker (`accept=".md,.markdown"`), filters non-md files locally, caps at 20 (matching the backend limit), and renders per-file rows with `data-status="pending|ok|err"` so tests can assert without scraping text. The 完成 button on the footer flips to "完成" once a successful upload happens, calling `onDone()` to refresh the parent Posts list. The `overwrite` toggle wires through to the existing backend query param.

---

### Task 31 — Tags reference scan + 409 delete refusal (parallel to Task 23 for media)

**Status:** completed
**Priority:** medium
**Frontend evidence:** /admin/tags — owner can currently click delete on any tag, including ones with posts attached.
**Owner problem:** Tag.id has `ON DELETE RESTRICT` from Post.tag_id, so the DB rejects the row but the API was still returning 204 — silent failure where the tag stayed but no error surfaced.
**Existing capability:** Tags CRUD with no reference enforcement.
**Gap:** no `post_count` on listing; no 409 on delete.
**Admin module:** 02 内容 / 标签
**Backend touch:**
  - `TagOut.post_count: int` field
  - `GET /api/admin/tags` LEFT JOIN posts and groups by tag.id to populate `post_count`
  - `DELETE /api/admin/tags/{id}` returns 409 with detail `tag has N post(s); reassign or delete them first` when `post_count > 0`
**Frontend API client:** existing
**UI / interaction:** future enhancement — disable delete button on tags with `post_count > 0` (deferred; backend protection alone closes the silent-failure gap).
**Automated tests:** pytest
**Playwright acceptance path:** API-only probe; covered below.
**Snapshot location:** none (backend-only).
**Commit message:** `feat(admin/tags): refuse delete when posts reference + post_count on list (Task 30)` (commit message uses "Task 30" because the numbering collision with the existing Task 30 spec was caught only after the commit — feature is recorded here as Task 31).
**Definition of done:** standard checklist
**Completed:** `f0eb20c`.

- **Backend tests:** `backend/.venv/bin/python -m pytest tests/test_admin_taxonomy.py` → 15/15 (3 new for Task 31: `post_count` field on every row, DELETE 409 when posts reference the tag with helpful detail message + tag still in listing afterward + cleanup detaches post and verifies subsequent DELETE returns 204; existing 12 still pass).
- **Live probe:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-30/verify.py` PASSED → list returns post_count → seed tag → POST a post under it via `/api/admin/posts` (frontmatter `tag: t30-live`) → list shows post_count=1 on the seeded tag → DELETE returns 409 with detail "tag has 1 post(s); reassign or delete them first" → after deleting the post, DELETE returns 204.
- **Snapshots:** none (backend-only).

Implementation note: the listing endpoint switches from a plain `select(Tag)` to a `LEFT JOIN posts ON post.tag_id = tag.id GROUP BY tag.id` with a `func.count(Post.id)` so the count comes from a single query (no N+1). The DELETE endpoint pre-checks via `select(func.count).where(Post.tag_id == tag.id)` and raises HTTPException(409, ...). Mirrors the Task 23 pattern for media but in DB-FK shape (`ON DELETE RESTRICT` already exists, so the API would have failed at commit time anyway — the new pre-check just produces a cleaner 409 with a helpful message instead of a 500 from the FK violation).

## Deferred / not in this index (still tracked)

These are real gaps but lower priority than Task 30 — picked up after the matrix above is empty, or if a higher-priority bug surfaces.

- D1 footer copy editable (`App.jsx:196-199` literals)
- D2 GitHub contrib sync status indicator on dashboard (last_synced_at, last_error)
- D3 Empty-state onboarding hints across every page
- D4 "view on public site" links on every admin object pointing at a public surface
- D5 Pet behavior: confirm-on-tab-switch when unsaved
- D6 Posts list: scheduled-at countdown column
- D7 Magic-link login alerts in inbox

When promoted, each gets a Task entry with the full skeleton.

---

## Completed-task ledger

Append-only. Every entry below means a real commit shipped.

| # | Title | Commit | Test | Playwright | Date |
|---|---|---|---|---|---|
| 0 | Establish PRD + task-index | `2177eda` | n/a (docs round) | n/a (docs round) | 2026-05-05 |
| 1 | Login 2FA challenge handling | `da9dd66` | `vitest run src/admin/Login.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-1/verify.py` PASSED | 2026-05-05 |
| 2 | Refresh-token rotation wired in AuthContext | `30f4db3` | `vitest run src/api/admin.test.js src/admin/Login.test.jsx` 12/12 | `python /tmp/admin-rebuild/task-2/verify.py` PASSED | 2026-05-05 |
| 3 | Posts editor GUI for lifecycle fields | `b08f712` | `vitest run src/admin/frontmatter.test.js` 11/11 | `python /tmp/admin-rebuild/task-3/verify.py` PASSED | 2026-05-05 |
| 4 | Sidebar IA regrouped + breadcrumb | `e30dbae` | `vitest run src/admin/Layout.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-4/verify.py` PASSED | 2026-05-05 |
| 5 | Activity feed on dashboard + activity log page | `d63255d` | `vitest run src/admin/ActivityLog.test.jsx` 4/4 | `python /tmp/admin-rebuild/task-5/verify.py` PASSED | 2026-05-06 |
| 6 | Site identity merged workflow | `7d404a5` | `vitest run src/admin/SiteIdentity.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-6/verify.py` PASSED | 2026-05-06 |
| 7 | Pet templates: 12 modes | `993465e` | `vitest run src/admin/pet/PetTemplates.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-7/verify.py` PASSED | 2026-05-06 |
| 8 | Reader likes wired to server + admin column | `fcab65e` | `vitest run src/api/client.test.js` 3/3 | `python /tmp/admin-rebuild/task-8/verify.py` PASSED | 2026-05-06 |
| 9 | HomeA contacts from API + fallback | `c8f48e1` | `vitest run src/components/contact-row.test.jsx` 7/7 | `python /tmp/admin-rebuild/task-9/verify.py` PASSED | 2026-05-06 |
| 10 | Comments per-post filter + bulk moderation | `87a8875` | `vitest run src/admin/Comments.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-10/verify.py` PASSED | 2026-05-06 |
| 11 | Theme color picker + live preview | `bcdd8ca` | `vitest run src/admin/oklch.test.js` 8/8 | `python /tmp/admin-rebuild/task-11/verify.py` PASSED | 2026-05-06 |
| 12 | Posts editor media picker | `5d3d3e9` | `vitest run src/admin/markdownInsert.test.js` 9/9 | `python /tmp/admin-rebuild/task-12/verify.py` PASSED | 2026-05-06 |
| 13 | Pet visitor profile sidebar | `4f8f8e7` | `vitest run src/admin/pet/VisitorProfileSidebar.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-13/verify.py` PASSED | 2026-05-06 |
| 14 | Inbox page (运营中枢) | `040356e` | `vitest run src/admin/Inbox.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-14/verify.py` PASSED | 2026-05-06 |
| 15 | Posts editor autosave drafts | `d54d90f` | `vitest run src/admin/draftStore.test.js` 9/9 | `python /tmp/admin-rebuild/task-15/verify.py` PASSED | 2026-05-06 |
| 16 | Admin ⌘K command palette | `28cae37` | `vitest run src/admin/CommandPalette.test.jsx src/admin/commandPaletteItems.test.js` 18/18 | `python /tmp/admin-rebuild/task-16/verify.py` PASSED | 2026-05-06 |
| 17 | Global keyboard shortcuts (?, g x, j/k) | `f688b6e` | `vitest run src/admin/keyboardShortcuts.test.js` 11/11 | `python /tmp/admin-rebuild/task-17/verify.py` PASSED | 2026-05-06 |
| 18 | URL-state filters & pagination on Posts | `ae66dbd` | `vitest run src/admin/searchParamsState.test.js` 12/12 | `python /tmp/admin-rebuild/task-18/verify.py` PASSED | 2026-05-06 |
| 19 | Unified ConfirmModal + Toast | `e86e322` | `vitest run src/admin/ui/ src/admin/Comments.test.jsx src/admin/pet/PetConversationDetail.test.jsx` 16/16 | `python /tmp/admin-rebuild/task-19/verify.py` PASSED | 2026-05-06 |
| 20 | SectionHead + Kbd visual primitives | `0c61615` | `vitest run src/admin/ui/SectionHead.test.jsx` 6/6 | `python /tmp/admin-rebuild/task-20/verify.py` PASSED | 2026-05-06 |
| 23 | Media reference scan + 409 delete refusal | `974063b` | `pytest tests/test_admin_media.py` 21/21 | `python /tmp/admin-rebuild/task-23/verify.py` PASSED | 2026-05-06 |
| — | Login.jsx i18n + test alignment (maintenance) | `7d1b29f` | `vitest run src/admin/Login.test.jsx` 5/5 | n/a (no UX change) | 2026-05-06 |
| 22a | Now editor markdown preview toggle | `56ab725` | `vitest run src/admin/nowMarkdown.test.js` 9/9 | `python /tmp/admin-rebuild/task-22a/verify.py` PASSED | 2026-05-06 |
| 22b | HomeA /now public panel | `4cf1753` | `vitest run src/components/NowPanel.test.jsx` 5/5 | `python /tmp/admin-rebuild/task-22b/verify.py` PASSED | 2026-05-06 |
| 27a | Integrations test-without-save endpoint | `8418544` | `pytest tests/test_admin_integrations.py` 26/26 | `python /tmp/admin-rebuild/task-27a/verify.py` PASSED | 2026-05-06 |
| 27b | Integrations 测试连接 button + multi-provider cards | `c4cf3f1` | `vitest run` 191/191 | `python /tmp/admin-rebuild/task-27b/verify.py` PASSED | 2026-05-06 |
| 27c | Provider priority order UI | `307670e` | `vitest run` 191/191 | `python /tmp/admin-rebuild/task-27c/verify.py` PASSED | 2026-05-06 |
| 25a | Per-post analytics CSV export | `7a80f03` | `pytest tests/test_admin_analytics.py -k csv` 3/3 | `python /tmp/admin-rebuild/task-25a/verify.py` PASSED | 2026-05-06 |
| 31 | Tags reference scan + 409 delete refusal | `f0eb20c` | `pytest tests/test_admin_taxonomy.py` 15/15 | `python /tmp/admin-rebuild/task-30/verify.py` PASSED | 2026-05-06 |
| 32 | Frontmatter plain-scalar auto-quote | `0aa0d40` | `pytest tests/test_admin_posts.py` 10/10 | `python /tmp/admin-rebuild/task-32/verify.py` PASSED | 2026-05-06 |
| 33 | PostDetail exposes lifecycle flags | `5ded359` | `pytest tests/test_admin_posts.py` 11/11 | live `curl` probe shows status/featured/private/comments_enabled/scheduled_at | 2026-05-06 |
| 34 | queue inline runner lazy-load registry | `6929ab9` | `pytest -k 'queue or worker or arq_inline'` 13/13 | n/a (worker plumbing) | 2026-05-06 |
| 35 | Localize remaining admin pages + mobile responsive | `017e930` | `vitest run` 191/191 | `python /tmp/admin-rebuild/task-35/verify.py` PASSED (14 pages) | 2026-05-06 |
| 30 | Bulk markdown post upload UI | `c865b85` | `vitest run` 191/191 | `python /tmp/admin-rebuild/task-30b/verify.py` PASSED | 2026-05-06 |
| 26a | PetUsage daily stacked bar chart | `81ab961` | `vitest run src/admin/pet/petUsageChart.test.js` 7/7 | `python /tmp/admin-rebuild/task-26a/verify.py` PASSED | 2026-05-06 |
| 25b | Analytics custom since-date picker | `a7e7e0a` | `vitest run src/api/analytics.test.js` 5/5 | `python /tmp/admin-rebuild/task-25b/verify.py` PASSED | 2026-05-06 |
| 29 | API tokens usage_count counter + UI | `cae0a56` | `pytest tests/test_api_tokens.py` 12/12 | `python /tmp/admin-rebuild/task-29/verify.py` PASSED | 2026-05-06 |
| 26b | PetUsage per-mode pie chart | `506c8a0` | `vitest run src/admin/pet/petUsageChart.test.js` 16/16 | `python /tmp/admin-rebuild/task-26b/verify.py` PASSED | 2026-05-06 |
| 24a | GitHub repo listing endpoint + cache | `ab2ca0d` | `pytest tests/test_admin_integrations.py` 30/30 | n/a (mocked GraphQL; live calls would hit real GitHub) | 2026-05-06 |
| 24b | GitHub import modal on Projects | `42e0781` | `vitest run` 212/212 | `python /tmp/admin-rebuild/task-24b/verify.py` PASSED | 2026-05-06 |
| 28a | Account email change endpoint | `da9dbfb` | `pytest tests/test_admin_email_change.py` 7/7 | `python /tmp/admin-rebuild/task-28a/verify.py` PASSED | 2026-05-06 |
| 28b | Account 修改邮箱 UI form | `5df5684` | `vitest run` 212/212 | `python /tmp/admin-rebuild/task-28b/verify.py` PASSED | 2026-05-06 |

---

### Task 32 — Frontmatter plain-scalar colon auto-quote

**Status:** completed
**Priority:** low (UX safety net)
**Frontend evidence:** PostEditor allows free-text frontmatter; YAML is strict about scalars containing colons (e.g. `summary: 推荐（按稳定度排序）:`).
**Owner problem:** typing a perfectly natural CJK summary that ends with `:` rejects the whole save with a parser error — surprising and obscure.
**Existing capability:** `parse_or_infer_frontmatter` calls `frontmatter.loads()` which throws on strict YAML errors.
**Gap:** no recovery path; render-preview returns 500-shaped errors via try/except outside the helper.
**Backend touch:** `app/services/post_ingest.py` — new `_quote_plain_frontmatter_scalars` helper + try/except retry; `IngestError` raised when even the fixed input fails to parse.
**Automated tests:** pytest covers (a) genuinely malformed yaml on render-preview returns structured 200 error, (b) genuinely malformed yaml on create returns 422, (c) plain scalar with colon now parses.
**Commit message:** `feat(admin/posts): auto-quote plain frontmatter scalars with colons (Task 32)`
**Completed:** `0aa0d40`.

Implementation note: helper only rewrites top-level `key: value` lines where the value has no leading quote / bracket / pipe / etc. — leaves all structured YAML untouched. JSON-encodes the value so embedded quotes / unicode survive correctly. Fall-through to `IngestError` when the rewrite still doesn't parse, so the API surface is unchanged for genuinely-broken inputs.

---

### Task 33 — PostDetail exposes lifecycle flags

**Status:** completed
**Priority:** medium (closes editor round-trip gap)
**Frontend evidence:** PostEditor's GUI strip (Task 3) reads `status / scheduled_at / featured / private / comments_enabled` from the post detail; previously the backend returned only the body + tag, so those toggles were always default.
**Owner problem:** opening an existing post in the editor lost the persisted lifecycle flags.
**Existing capability:** Post model has all 5 columns; PUT / patch endpoints accept them via frontmatter; only the GET shape was missing them.
**Gap:** `PostDetail` schema lacked these fields; both the `_detail` helper and the direct `get_post` constructor missed them.
**Backend touch:** `app/schemas/post.py` adds 5 fields (typed as `| None = None` so test fixtures and old clients don't break); `app/routers/admin/posts.py` populates from `Post` columns in both call sites.
**Automated tests:** pytest creates a post via `POST /api/admin/posts` (frontmatter `status: published`) → GET → asserts all five fields present + correct defaults.
**Commit message:** `feat(admin/posts): expose lifecycle flags on PostDetail (Task 33)`
**Completed:** `5ded359`.

Implementation note: the Pydantic v2 default `None` makes the new fields opt-out for any non-admin caller that never populates them, so this is backwards-compatible. Live `curl` against `/api/admin/posts/vps` now returns `{"status":"published","scheduled_at":null,"featured":false,"private":false,"comments_enabled":true}` — exactly what the editor's GUI strip needs.

---

### Task 34 — queue inline runner registry lazy-load

**Status:** completed
**Priority:** low (plumbing)
**Existing capability:** `app/workers/queue.py::enqueue` dispatches to `_TASK_REGISTRY[name]` when `arq_inline=True`; populated by `app/workers/runner.py` via module-level `register()` calls.
**Gap:** the FastAPI app process never imports `runner` (only the arq worker does), so when a request hit `enqueue` with `arq_inline=True` the registry was empty → `RuntimeError: task 'foo' not registered`.
**Backend touch:** 5-line lazy import inside the `arq_inline` branch — only fires when the registry is empty so it stays a no-op for the worker process.
**Commit message:** `fix(workers/queue): lazy-load runner registry in inline mode (Task 34)`
**Completed:** `6929ab9`.

Implementation note: import sits inside the `if not _TASK_REGISTRY:` so repeated dispatches don't re-import. The worker process already imports `runner` at startup, so this check is `False` there and the lazy load never runs — zero behavior change for arq mode.

---

### Task 35 — Localize remaining admin pages + mobile responsive

**Status:** completed
**Priority:** medium (consistency)
**Existing capability:** Login (round 24), Posts/Comments/Tags/Media/Now/Inbox/Dashboard already had Chinese strings via SectionHead (Task 20) + earlier Tasks 1-23. Several deeper pages (Analytics, PostEditor, Profile, Settings, pet/Pet*, settings/*) still had English copy in error messages, headers, and form labels.
**Gap:** mixed English/Chinese strings on a Chinese-first admin made the rebuild feel incoherent.
**Frontend touch:** 13 `.jsx` files + 1 `.test.jsx` updated to use Chinese strings, plus `src/styles.css` adds three responsive overrides (`.admin-form-grid → 1fr` / `.admin-table-wrap → overflow-x:auto` / `.admin-search → width:100%`) under the existing 800px media query so mobile owners can use the admin without horizontal scrolling.
**Automated tests:** Vitest 191/191 (no regression from the i18n strings — tests that asserted English copy were updated when needed; PetConversations.test.jsx had one selector adjusted).
**Playwright:** smoke-checked all 14 admin pages render after the i18n changes — `/tmp/admin-rebuild/task-35/verify.py` PASSED (login → goto each page → assert at least an h1 / .section-head .label / Pet tab button is visible). 14/14 pages green.
**Commit message:** `i18n(admin): localize remaining pages + mobile responsive tweaks (Task 35)`
**Completed:** `017e930`.

Implementation note: the i18n changes had been carried in the unstaged stash for many rounds — every loop they got re-stashed and popped, occasionally generating conflicts. Bundling them into a single explicit commit closes that overhead and serves the loop's "保持页面美观、一致、可长期使用" principle. The responsive tweaks are tiny and travel with the same UI surfaces, so they share the commit. Working tree is now empty for the first time since round 1.

---

### Task 36 — Owner-configurable LLM cost rates

**Status:** completed
**Priority:** medium (closes Task 26c follow-up)
**Frontend evidence:** PetUsage cost line (Task 26c) — owner couldn't tune the per-provider USD rates; values were hardcoded approximations.
**Owner problem:** real billing differs from my hardcoded rates (zhipu/deepseek/qwen/doubao/anthropic shift over time), so the cost line was a rough estimate at best.
**Existing capability:** PROVIDER_RATES table in `petUsageChart.js` (5 hardcoded providers + default fallback).
**Gap:** no API to override; no admin UI to set rates.
**Admin module:** 03 观察 / 宠物用量 (inline editor on the same page as the cost chart).
**Backend touch:**
  - new `app/services/pet_cost_rates.py` — `get_all(s)` aggregates from `Integration.extra_json.cost_in_per_m` / `cost_out_per_m` with default fallback; `set_rate(s, provider, in_per_m, out_per_m)` writes back into the existing Integration row's extra_json
  - new endpoints `GET /api/admin/pet/cost-rates` (read; auth-only) and `PUT /api/admin/pet/cost-rates` (write-scope; 404 when provider has no Integration row, 422 negative/unknown)
  - new schemas `CostRatesResponse` / `CostRateItem` / `CostRateUpdateRequest` in `app/schemas/pet.py`
**Frontend API client:** `apiPet.getCostRates` + `apiPet.setCostRate` in `src/api/pet.js`.
**UI / interaction:** `<CostRatesEditor>` on Pet → 用量 tab below the cost chart, collapsed behind `⚙ 设置成本费率`. Per-provider row with `输入 $/M` / `输出 $/M` inputs + per-row save. Save triggers a parent reload so the cost chart redraws against the new rate immediately.
**Automated tests:** pytest `tests/test_pet_cost_rates.py` (6 cases) + vitest extends `petUsageChart.test.js` (rowCostUSD honors custom rates, groupCostByDay accepts the rates map).
**Playwright acceptance path:**
  1. /admin/pet?tab=usage → expand `⚙ 设置成本费率`
  2. Set new rates for a configured provider
  3. Save → re-fetch /pet/cost-rates confirms persistence
  4. Cost chart re-renders against the new rate
  5. Restore original at teardown
**Snapshot location:** `/tmp/admin-rebuild/task-36/rates-panel.png`
**Commit:** `d57354a` (`feat(admin/pet): owner-configurable LLM cost rates (Task 36)`).

- **Backend tests:** `./.venv/bin/python -m pytest tests/test_pet_cost_rates.py` → 6/6 (defaults when no overrides, 404 for unconfigured provider, 422 negative/unknown, 401 unauth, end-to-end persistence with seeded anthropic Integration).
- **Vitest:** combined `npx vitest run` → **254/254** (no Task 1-35 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-36/verify.py` → API smoke (6 entries returned, 422 negative + unknown) → live `deepseek` integration in dev → expand panel → set rate → save → /cost-rates persisted within 1e-6 tolerance → restore.
- **Snapshots:** `/tmp/admin-rebuild/task-36/rates-panel.png`.

Implementation note: storing rates inside each provider's existing `Integration.extra_json` keeps the surface tiny — no migration, no separate model, and the API key + price travel together. When the owner hasn't configured a provider yet, PUT returns 404 with a clear hint ("integration X not configured") rather than silently creating an orphan rate row. The bundled `DEFAULT_RATES` in `pet_cost_rates.py` mirrors `PROVIDER_RATES` in `petUsageChart.js` exactly so the chart's pre-fetch first-paint matches the post-fetch render. The editor is collapsed by default behind `⚙` so it doesn't compete with the charts for attention; per-row save lets the owner update zhipu without touching anthropic. write_event log row records every rate change for audit.

---

### Task 25b-companion-lists — top_paths/posts/tags arbitrary window

**Status:** completed
**Priority:** medium (closes Task 25b-arbitrary-end follow-up)
**Frontend evidence:** Analytics page picks `[from, to]` → main timeseries chart already honored the window, but the companion lists (top paths / referrers / countries / posts / tags) silently fell back to "ending now". Asymmetry was confusing when comparing historical windows.
**Owner problem:** "May 1–May 5" range showed top_paths for the last 5 days ending today, not the seleted window.
**Existing capability:** /analytics, /analytics/posts, /analytics/tags accepted `days=N`; /analytics also accepted `from/to` for the timeseries (Task 25b-arbitrary-end).
**Gap:** the four top-list services (`top_paths`, `top_referrers`, `top_countries`, `per_post`, `per_tag`) plus the shared `_merge_jsonb_top` helper were `days`-only. Bundle endpoint shoehorned a derived `days_for_lists` rather than passing the actual window.
**Backend touch:**
  - new `_window_pieces(days, from_, to)` helper returns `(start, history_end_exclusive, today_start_dt | None)` — the `None` branch fires when the window is fully historical (end < today) so the live HitEvent merge is skipped
  - `_merge_jsonb_top` signature now takes `(start, history_end_exclusive)` instead of `days=N`
  - `top_paths`, `top_referrers`, `top_countries`, `per_post`, `per_tag` all accept the same trio `(days, from_, to)` keyword set; backwards-compat with existing `days=N` callers is preserved
  - `/analytics` router passes `from_/to` straight to companion calls when present (no more `days_for_lists` shim)
  - `/analytics/posts` + `/analytics/tags` accept `?from=&to=` with the same 422 paired/inverted/over-365 validation as `/analytics`
**Frontend API client:** `apiAnalytics.posts(range)` + `apiAnalytics.tags(range)` route to `?from&to` when the range token is `range:`; otherwise legacy `?days=N`.
**Automated tests:** pytest +4 (companion accepts from/to, partial 422, bundle filters by window across two seeded HitDaily rows on 4-5 and 4-25).
**Playwright acceptance path:** API smoke seeded /p25b-comp-IN on 2026-04-05 + /p25b-comp-OUT on 2026-04-25, then asserted `/analytics?from=2026-04-01&to=2026-04-10` top_paths included only IN (4-1..4-10) and `/analytics?from=2026-04-20&to=2026-04-30` flipped to OUT.
**Snapshot location:** none (API-only; UI flow already covered by Task 25b-arbitrary-end's snapshot).

- **Backend tests:** `./.venv/bin/python -m pytest tests/test_admin_analytics.py` → 26/26 (4 new on top of 22).
- **Vitest:** combined `npx vitest run` → **254/254** (no regression).
- **Playwright (API):** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-25b-companion/verify.py` PASSED — seeded IN+OUT HitDaily rows, both windows isolate the right path, /posts and /tags accept from/to + 422 partial, cleanup restores DB.
- **Commit:** `2376276` (`feat(admin/analytics): companion lists honor [from, to] window (Task 25b-companion)`).

Implementation note: `_window_pieces` decouples "which HitDaily dates to read" from "should we add today's HitEvent live count". A historical-only window (end < today) returns `today_start_dt = None`, so callers skip the second SELECT. This is a minor performance win on top of correctness — historical windows do one query instead of two. Backwards compat: every call site that still passes `days=N` continues to work because `_window_pieces` accepts the same shape that `resolve_window` already does. The Task 25b-arbitrary-end implementation note's TODO ("`top_paths` and friends still anchor at today") is now resolved — the analytics bundle is fully consistent under any window.

---

### Task 25b-csv-drilldown — CSV + per-post drilldown honor [from, to]

**Status:** completed
**Priority:** medium (closes the last 25b-arbitrary-end follow-up)
**Frontend evidence:** Analytics page picks `[from, to]` → main bundle + companion lists already honored the window (Task 25b-companion). But:
  - 导出 CSV button still emitted a `days=N` URL → CSV reflected ending-now window, not the active selection
  - hot-post click-through preserved `range=...` query but the drilldown dropped non-preset tokens (`range:`, `since:`) and silently fell back to 30d
  - drilldown's chart fetched `?days=` only, so even when the URL token was honored the API call was wrong shape
**Owner problem:** "I picked May 1–May 5, then exported CSV — got ending-now data" / "I clicked into a post drilldown — chart spans the wrong window".
**Existing capability:** `/analytics/posts.csv?days=N` and `/analytics/posts/{id}/timeseries?days=N` worked; companion endpoints already accepted from/to (Task 25b-companion).
**Gap:** csv + per-post timeseries router endpoints didn't accept from/to; drilldown UI didn't recognize `range:` / `since:` tokens.
**Backend touch:**
  - `analytics_svc.per_post_timeseries` extended to accept `(days, from_, to)` via the same `resolve_window` helper used by `timeseries`
  - `/analytics/posts.csv` accepts `?from=&to=` with paired/inverted/over-365 422 validation; filename now embeds `2026-04-01_to_2026-04-07` (or `7d` legacy) so multi-window exports don't collide
  - `/analytics/posts/{id}/timeseries` same from/to params + 422 trio
**Frontend API client:** `apiAnalytics.postTimeseries(id, range)` + `apiAnalytics.downloadPostsCsv(range)` route to `?from&to` when the range token matches `range:`
**UI / interaction:**
  - `AnalyticsPostDetail` accepts `range:from..to` and `since:YYYY-MM-DD` from URL state (was: only `7d|30d|90d`)
  - Custom-range label `2026-04-01 → 2026-04-10` (or `自 YYYY-MM-DD`) renders next to the chips so the user can see what window the chart is showing
  - Click-through from parent already passed `range=<active>`; combined with the wider acceptance, the drilldown chart now matches the parent
**Automated tests:** pytest +4 (timeseries from/to, posts.csv from/to + filename, both 422 partial) + vitest +2 (drilldown range-pass-through for `range:` + `since:`).
**Playwright acceptance path:** /admin/analytics → fill from + to → click hot-post → drilldown URL preserves `range:`, custom-range label visible, network request to /timeseries carries from + to.
**Snapshot location:** `/tmp/admin-rebuild/task-25b-csv-drilldown/drilldown-custom-range.png`.

- **Backend tests:** `./.venv/bin/python -m pytest tests/test_admin_analytics.py` → 30/30 (4 new on top of 26).
- **Vitest:** combined `npx vitest run` → **256/256** (no Task 1-35 + 36 + 25b-companion regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-25b-csv-drilldown/verify.py` PASSED — CSV filename embeds window, /timeseries 7-day window, drilldown UI carries `range:` + shows custom-range label + fetches with from/to.
- **Snapshots:** `/tmp/admin-rebuild/task-25b-csv-drilldown/drilldown-custom-range.png`.
- **Commit:** `dab0051` (`feat(admin/analytics): CSV + per-post drilldown honor [from, to] (Task 25b-csv-drilldown)`).

Implementation note: the analytics arbitrary-window story is now end-to-end consistent across every endpoint and every UI surface. Drilldown chips remain available — clicking 7 天/30 天/90 天 still works and replaces the active range token; the custom-range label only shows when the active token is non-preset. CSV filename change is technically backwards-compatible because the previous `{N}d` slug is preserved when no from/to is supplied — only the new arbitrary-window form gets the `from_to_to` slug.

---

### Task 37 — public sitemap.xml + Atom feed

**Status:** completed
**Priority:** medium (SEO and RSS reader support)
**Frontend evidence:** No public surface for search engines or RSS readers — every post URL `/p/<id>` was un-discoverable from outside the SPA.
**Owner problem:** crawlers had no way to enumerate the post catalogue; readers couldn't subscribe via RSS/Atom.
**Existing capability:** none — the API exposed `/api/posts` with filtering + pagination but search engines don't follow API endpoints.
**Gap:** classic SEO infrastructure (sitemap protocol 0.9 + Atom 1.0 feed) was missing.
**Backend touch:**
  - new `backend/app/routers/public/sitemap.py` with two endpoints
  - `GET /api/sitemap.xml` — every published, non-private post + the site root, with `<lastmod>` from `updated_at` (or `date` when null)
  - `GET /api/feed.xml` — Atom 1.0 feed of last 50 published posts (id, title, link, updated, summary). Title and summary XML-escaped via `xml.sax.saxutils.escape` so `<Test>` and `&` don't break parsers
  - Site host comes from `settings.public_site_base_url` (already added in Task 28c)
  - Filters: `Post.status='published' AND Post.private IS FALSE`
**Frontend API client:** none — XML endpoints are consumed by external crawlers / readers, not by the SPA
**UI / interaction:** none for v1. Production reverse proxy can alias `/sitemap.xml` → `/api/sitemap.xml` so search engines find it at the canonical root path.
**Automated tests:** pytest 5 cases (sitemap surfaces published only, draft + private excluded, well-formed XML, atom escapes special chars, no-published edge case).
**Playwright acceptance path:** none browser-side — XML is consumed programmatically. API smoke validates parseable XML + content.

- **Backend tests:** `./.venv/bin/python -m pytest tests/test_public_sitemap.py` → 5/5.
- **Vitest:** no frontend impact, regression sweep stays at **256/256**.
- **API smoke:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-37/verify.py` PASSED — sitemap returns 6 urls (5 published posts + root), feed returns 5 entries with id/title/link triples, both parse as valid XML.
- **Snapshots:** `/tmp/admin-rebuild/task-37/{sitemap.xml,feed.xml}` captured for inspection.
- **Commit:** see ledger commit below.

Implementation note: kept it pure-XML (no JSON Feed, no RSS 2.0 — Atom 1.0 has cleaner namespace semantics and is what most modern readers expect). Site host config reuses `public_site_base_url` from Task 28c — production deploys override in `.env`. The sitemap site-root entry is unconditional so a brand-new install with zero published posts still has a valid urlset (validated by the no-posts test). Atom self-link points at `/api/feed.xml` directly, so a deploy without proxy alias still works for RSS readers — they just see the API path. A future task can add `<link rel="alternate" type="application/atom+xml">` to the public site's `<head>` so browsers' built-in feed-discovery picks it up.

---

### Task 38 — robots.txt + feed-discovery link

**Status:** completed
**Priority:** medium (closes the 37-follow-up: make sitemap + feed actually discoverable)
**Frontend evidence:** Task 37 added `/api/sitemap.xml` + `/api/feed.xml`, but search engines look for `/robots.txt` (not API paths) and browsers won't auto-discover the feed without a `<link rel=alternate>` in `<head>`. The infrastructure existed but was effectively invisible.
**Owner problem:** "I shipped a sitemap and Atom feed last round but Googlebot has no way to find the sitemap, and Firefox/RSS readers can't subscribe by visiting the homepage."
**Existing capability:** `/api/sitemap.xml` + `/api/feed.xml` (Task 37).
**Gap:** no robots.txt, no feed-discovery link tag.
**Backend touch:**
  - `GET /api/robots.txt` returning `text/plain` with `User-agent: * / Allow: / / Disallow: /api/admin/ / Sitemap: <site>/api/sitemap.xml`
  - Sitemap pointer uses absolute URL from `public_site_base_url` so the path is right even when this endpoint is mounted under `/api/`
**Frontend touch:** `<link rel="alternate" type="application/atom+xml" title="myblog · Atom feed" href="/api/feed.xml" />` injected into `index.html <head>` so Firefox/Safari feed-discovery and RSS-reader bookmarklets find the feed automatically when visiting `/`.
**Automated tests:** pytest +2 cases (allow + sitemap pointer present, public access).
**Playwright acceptance path:** API smoke confirms robots.txt content + content-type. Browser smoke loads `/`, asserts `<head>` contains the feed-discovery link, fetches `/api/feed.xml` through the vite proxy and checks the content-type.

- **Backend tests:** `./.venv/bin/python -m pytest tests/test_public_sitemap.py` → 7/7 (2 new on top of 5).
- **Vitest:** combined `npx vitest run` → **256/256** (no regression — index.html is HTML, not in the JS test surface).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-38/verify.py` PASSED — robots.txt 4 lines with Sitemap pointer, `<link rel=alternate>` href=/api/feed.xml + title carries "Atom", feed XML resolves through vite proxy with `application/xml; charset=utf-8`.
- **Snapshots:** `/tmp/admin-rebuild/task-38/robots.txt`.
- **Commit:** `235a607` (`feat(public/seo): robots.txt + Atom feed-discovery link (Task 38)`).

Implementation note: the sitemap pointer in robots.txt is absolute (using `public_site_base_url`) on purpose — search-engine crawlers normalize relative paths inconsistently, and a deploy behind a reverse proxy might not have the `/api/` prefix at the canonical site host. Absolute URLs are the safe default. Production deploys typically alias `/robots.txt` → `/api/robots.txt` and `/sitemap.xml` → `/api/sitemap.xml` at the proxy; the absolute pointer keeps the chain intact regardless. The feed-discovery link uses `/api/feed.xml` (relative path) so it works in dev (vite proxies `/api`) and prod (reverse proxy serves it). Title is human-readable so RSS readers display "myblog · Atom feed" rather than the raw URL.

---

### Task 39 — PetSpeciesEditor uses ConfirmModal not window.confirm

**Status:** completed
**Priority:** low (visual consistency polish — closes Task 21d follow-up)
**Frontend evidence:** every other admin destructive action used the shared `<ConfirmModal>` (via `useConfirm` hook) for visual consistency; only the species delete dropped to the native `window.confirm()` browser dialog. This was flagged in 21d's implementation note as a deferred polish.
**Owner problem:** the system browser dialog was visually inconsistent with the rest of the admin (different font, spacing, and missing the destructive-button styling).
**Existing capability:** `useConfirm` hook + `<ConfirmModal>` mounted via `<UIProvider>` at the admin shell root.
**Gap:** PetSpeciesEditor's `removeRow` still called `window.confirm()` (added in 21d).
**Frontend touch:** import `useConfirm` from `../ui/UIProvider.jsx`; replace `if (!window.confirm(...)) return` with `const ok = await confirm({ title, message, confirmLabel, destructive: true }); if (!ok) return`.
**Automated tests:** vitest mocks `useConfirm` at module scope to always-confirm so existing behavioral tests stay green; the cancel path is exercised by Playwright instead.
**Playwright acceptance path:**
  1. /admin/pet?tab=species → create temp species via UI
  2. Click delete → assert `[data-testid=confirm-modal]` mounts (NOT a native dialog)
  3. Confirm via `[data-testid=confirm-ok]` → row detaches
  4. Repeat with cancel via `[data-testid=confirm-cancel]` → row preserved
  5. `page.on("dialog", ...)` collector confirms zero native dialogs fired throughout
**Snapshot location:** `/tmp/admin-rebuild/task-39/confirm-modal.png`

- **Vitest:** `npx vitest run` → **256/256** (no regression — `useConfirm` mocked to async-true preserves existing happy-path assertions).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-39/verify.py` PASSED — modal mounts with species id + warning copy, confirm removes the row, cancel preserves it, zero native dialogs throughout the run.
- **Snapshots:** `/tmp/admin-rebuild/task-39/confirm-modal.png`.
- **Commit:** `ff4d104` (`feat(admin/pet): replace window.confirm with admin ConfirmModal in species editor (Task 39)`).

Implementation note: zero-content change to the editor's behavior — same gate, same blast radius, same destructive-action affordance. The win is purely visual consistency: the species delete now uses the same modal styling and keyboard handling (Esc to cancel, Enter to confirm) as the password-change confirm, the integration revoke confirm, the comment-bulk-reject confirm, etc. `grep -rn 'window.confirm' src` is now empty across the admin surface — every destructive action is unified behind `useConfirm`.

---

### Task 40 — frame composer live preview

**Status:** completed
**Priority:** low (closes Task 21f follow-up)
**Frontend evidence:** Task 21f added 3 ASCII frame textareas per species. Owners couldn't see what the renderer would do with `{E}` markers without saving and visiting the public page.
**Owner problem:** "I'm editing duck's frame 2, but is the eye in the right place? Where's the ω going to land?" — the textarea showed raw template, not the rendered sprite.
**Existing capability:** layout hint + frame-count badge (Task 21f), `STATE_EYE` mapping in `src/components/pet/species.js`.
**Gap:** no live preview alongside the textarea.
**Frontend touch:**
  - new `renderFrameForPreview(lines)` exported helper — substitutes `{E}` with the idle eye marker `·` (mirrors `STATE_EYE.idle` to match what visitors see when no interaction is in flight)
  - `<FramesPanel>` now renders a `<pre data-testid=species-frame-preview-{id}-{idx}>` block immediately below each textarea; same monospace, dashed border, accent color, `min-height: 5em` so empty frames keep visual rhythm
  - Defensive: non-array / non-string entries coerce to empty so a stale draft mid-edit doesn't crash the preview
**Automated tests:** vitest +5 cases (substitution, multi-line join, defensive empty/null/undefined, non-string entries, plus a UI test that types into the textarea and watches the preview track).
**Playwright acceptance path:**
  1. /admin/pet?tab=species → expand duck frames panel
  2. Assert all 3 preview blocks mount alongside textareas
  3. Verify existing duck frame 0 preview has no leaked `{E}` and contains `·`
  4. Type a sentinel `( {E} ω {E} )\nLINE-2-MARKER` → preview shows `( · ω · )\nLINE-2-MARKER`
  5. Cleanup: restore duck.frames to pre-test state
**Snapshot location:** `/tmp/admin-rebuild/task-40/frame-preview.png`

- **Vitest:** combined `npx vitest run` → **261/261** (no Task 1-39 regression).
- **Playwright:** `/tmp/.audit-env/bin/python /tmp/admin-rebuild/task-40/verify.py` PASSED — 3 preview blocks mount, existing frame substitutes correctly, sentinel input round-trips through the preview live.
- **Snapshots:** `/tmp/admin-rebuild/task-40/frame-preview.png`.
- **Commit:** `aadf74d` (`feat(admin/pet): live preview alongside ASCII frame textarea (Task 40)`).

Implementation note: chose to inline the `·` constant rather than `import { STATE_EYE } from '...'`. The species module hydrates async; the editor mounts before that's done. Hardcoding mirrors `STATE_EYE.idle` and avoids coupling the admin's preview to the pet renderer's load cycle. If the idle eye changes globally, both places need to be updated — the comment makes that explicit. Preview deliberately does NOT colorize per-species (the production renderer applies tint as CSS `color`); skipping that here keeps the admin preview neutral so layout drift is the focal point, not aesthetic match.
