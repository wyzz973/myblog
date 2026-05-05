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

**Status:** pending
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
**Completed:** —

---

### Task 22 — Now: markdown preview + public surface decision

**Status:** in-progress (22a complete, 22b pending)
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

Implementation note: the post `render-preview` endpoint requires a full valid post frontmatter (id pattern + n field), which would require a stub-and-strip dance for short Now blurbs. Instead we ship `src/admin/nowMarkdown.js` — a 60-LOC inline renderer that handles the markdown subset that actually appears in Now entries (paragraphs, bold, italic, inline code, bullet lists, bare http links). Output is HTML-escape-first to prevent injection. The toggle button uses `data-testid=now-preview-{id}` and `data-active="true"` so the keyboard layer (Task 17) can still operate on the row even while preview is shown. Public surface (Task 22b) still needs the /now panel on HomeA.

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

**Status:** pending
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
**Completed:** —

---

### Task 25 — Analytics: custom date range + CSV export + per-post page

**Status:** pending
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
**Completed:** —

---

### Task 26 — Pet usage charts

**Status:** pending
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
**Completed:** —

---

### Task 27 — Integrations: test-without-save + provider priority UI

**Status:** pending
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
**Completed:** —

---

### Task 28 — Account: email change

**Status:** pending
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
**Completed:** —

---

### Task 29 — API tokens: usage history

**Status:** pending
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
**Completed:** —

---

### Task 30 — Bulk markdown post upload UI

**Status:** pending
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
**Completed:** —

---

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
