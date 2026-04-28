# Phase 6b — Analytics Design Spec

> **Phase 6 carve-up**: P6 split into three serial sub-projects. P6a (Media) merged 2026-04-28. This is **P6b (Analytics)**. P6c (Danger zone) is next.

## 1. Goal

Capture page-view beacons from the SPA, aggregate them nightly into daily summaries, and expose admin endpoints powering both the dashboard KPI tiles and the analytics deep-dive screen of the prototype admin console:

- Public `POST /api/hit` beacon — cookie-less, IP-only for server-side dedup, never persisted.
- Two new tables: `hit_events` (raw, 30-day retention) + `hit_daily` (aggregate, retained indefinitely).
- ARQ nightly rollup at 03:00 UTC: hit_events → hit_daily, then truncate raw rows older than 30 days.
- Four admin GET endpoints: dashboard KPI bundle, analytics summary bundle, per-post views, per-tag aggregates.

## 2. Out of scope

- Realtime "live visitors" counter — daily granularity is enough for a personal blog.
- Conversion funnels / multi-step session tracking.
- Bot detection beyond a simple UA blocklist regex (no fingerprinting, no challenge pages).
- IP-based geo without an HTTP-header source — Country comes from `CF-IPCountry` only; absent → NULL. No GeoIP DB.
- Beyond-30-day raw retention. Historical raw queries unsupported.
- Per-hit referrer/country in admin views — only top-N aggregates (referrer/country) and per-(date, path) totals are exposed.
- Public analytics readout. Only admin can read aggregates.

## 3. Data model

### 3.1 `hit_events` (raw stream)

```sql
CREATE TABLE hit_events (
    id          BIGSERIAL PRIMARY KEY,
    path        VARCHAR(512) NOT NULL,
    referrer    VARCHAR(512),
    country     CHAR(2),                                              -- ISO 3166-1 alpha-2 from CF-IPCountry; NULL if absent
    post_id     VARCHAR(64) REFERENCES posts(id) ON DELETE SET NULL,  -- denormalized post-page hint, sent by frontend
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_hit_events_created_at ON hit_events (created_at DESC);
CREATE INDEX ix_hit_events_post_id    ON hit_events (post_id) WHERE post_id IS NOT NULL;
```

`BIGSERIAL` because hit_events accumulates per-PV; even a modest blog hits millions over years and a 32-bit PK would be a foot-gun.

### 3.2 `hit_daily` (daily aggregate)

```sql
CREATE TABLE hit_daily (
    date            DATE NOT NULL,
    path            VARCHAR(512) NOT NULL,
    hits            INTEGER NOT NULL,
    post_id         VARCHAR(64) REFERENCES posts(id) ON DELETE SET NULL,
    referrers_top   JSONB NOT NULL DEFAULT '[]'::jsonb,    -- [{r: "...", n: 12}], length ≤ 10
    countries_top   JSONB NOT NULL DEFAULT '[]'::jsonb,    -- [{c: "US", n: 8}], length ≤ 10
    PRIMARY KEY (date, path)
);
CREATE INDEX ix_hit_daily_date    ON hit_daily (date DESC);
CREATE INDEX ix_hit_daily_post_id ON hit_daily (post_id) WHERE post_id IS NOT NULL;
```

`post_id` is denormalized at rollup time from the day's hit_events (every event for a given path either had post_id or didn't; if mixed, the rollup picks the first non-NULL).

`referrers_top` / `countries_top` are computed by the rollup as top-10 by count. Each row is a JSONB array of objects.

### 3.3 ORM models

- `app/models/hit_event.py` — `HitEvent`
- `app/models/hit_daily.py` — `HitDaily` (composite PK declared via `mapper_args`)

### 3.4 Migration `0006_analytics`

Forward + reversible. Creates both tables + 4 indexes. Downgrade drops indexes then tables.

## 4. Write path

### 4.1 `app/services/hits.py`

```python
import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HitEvent, Post

BOT_RE = re.compile(
    r"(bot|crawler|spider|curl|wget|httpclient|python-requests)", re.I
)

async def record(
    s: AsyncSession,
    *,
    redis,
    path: str,
    referrer: str | None,
    ip: str,
    country: str | None,
    user_agent: str | None,
    post_id: str | None,
) -> bool:
    """Record one hit. Returns True if persisted, False if filtered.

    Filters in order:
      1. UA bot regex
      2. Redis 60s dedup on hash(ip + "|" + path)

    Side notes:
      - Validates `post_id` exists in `posts` table. If not, falls back to NULL.
      - Validates `country` is exactly 2 ASCII uppercase letters. Otherwise NULL.
      - IP is used for dedup only; never written to DB.
    """
```

Filter order matters: bot UA first (cheap regex) so we don't burn Redis ops on bot floods.

`country` validation: `re.match(r"^[A-Z]{2}$", country)` else None.

`post_id` validation: SELECT 1 FROM posts WHERE id=$1 (cached in-process for the request lifetime is fine; one round-trip per beacon is acceptable). If not found, fall back to NULL — defends against forged FK errors and post deletions racing with beacons.

### 4.2 `POST /api/hit` (public)

`app/routers/public/hits.py`:

```python
@router.post("/hit", status_code=204)
async def record_hit(
    req: HitRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> Response:
    ip = request.headers.get("X-Forwarded-For", request.client.host or "").split(",")[0].strip()
    country = (request.headers.get("CF-IPCountry") or "").upper() or None
    user_agent = request.headers.get("User-Agent")

    await hits_svc.record(
        s,
        redis=redis,
        path=req.path,
        referrer=req.referrer,
        ip=ip,
        country=country,
        user_agent=user_agent,
        post_id=req.post_id,
    )
    await s.commit()  # commits at most one INSERT, or no-op if filtered
    return Response(status_code=204)
```

`HitRequest`: `{path: str (max 512), referrer?: str (max 512), post_id?: str (max 64)}`.

**Always returns 204.** Filtered or accepted, the response is identical so a noisy client cannot probe filter state.

**Rate limit**: piggyback on the P3 IP-bucket limiter (60 req/min/IP global). The 60s Redis dedup is per (ip, path) — not the same as the global IP cap.

## 5. ARQ rollup

### 5.1 `app/workers/tasks.py` — new task

```python
from datetime import UTC, date, datetime, timedelta

async def analytics_rollup_task(ctx, target_date: str | None = None) -> dict:
    """Rolls hit_events of `target_date` (default = yesterday in UTC) into hit_daily.

    Steps for `target_date = D`:
      1. SELECT path, post_id, COUNT(*) FROM hit_events
         WHERE created_at >= D 00:00 UTC AND created_at < D+1 00:00 UTC
         GROUP BY path, post_id
      2. For each (path, post_id, count): also compute top-10 referrers and top-10 countries
         (separate queries with LIMIT 10).
      3. UPSERT hit_daily (PK = (date, path)). On conflict, replace hits / referrers_top /
         countries_top / post_id (post_id picked as MIN(post_id)).
      4. After rollup, DELETE FROM hit_events WHERE created_at < (today - 30 days).

    Idempotent: re-running with the same target_date overwrites hit_daily rows.
    Returns {date, paths_rolled, rows_truncated}.
    """
```

`target_date` is passed as ISO string for ARQ-serializability.

### 5.2 Cron registration

ARQ `WorkerSettings.cron_jobs` adds:

```python
from arq.cron import cron
cron_jobs = [cron(analytics_rollup_task, hour=3, minute=0)]  # 03:00 UTC daily
```

Tests with `ARQ_INLINE=true` invoke `analytics_rollup_task(ctx, target_date)` synchronously.

### 5.3 Event log

The task writes one `analytics.rollup` row at the end with `meta = {date, paths_rolled, rows_truncated}`. Failures (any exception) write `analytics.rollup_failed` with `meta = {date, error}`.

## 6. Read path — `app/services/analytics.py`

```python
@dataclass
class DashboardKPIs:
    hits: HitsKPI                # today / last_7d / last_30d
    likes: LikesKPI              # total / last_7d
    comments: CommentsKPI        # total / pending
    posts: PostsKPI              # published / draft / scheduled
    media: MediaKPI              # count

async def dashboard_kpis(s) -> DashboardKPIs

async def timeseries(s, *, days: int) -> list[DayPoint]
    """Daily total hits for last N days (today computed live from hit_events,
    historical days from hit_daily). Returns days items even when 0."""

async def top_paths(s, *, days: int, limit: int = 10) -> list[PathHits]
async def top_referrers(s, *, days: int, limit: int = 10) -> list[ReferrerHits]
async def top_countries(s, *, days: int, limit: int = 10) -> list[CountryHits]
    """top_referrers/top_countries: read JSONB top arrays from hit_daily for the
    window, merge into a global top-N. Today's contribution comes from
    hit_events GROUP BY."""

async def per_post(s, *, days: int) -> list[PostHits]
    """SELECT hit_daily.post_id, posts.title, SUM(hit_daily.hits) AS hits
       FROM hit_daily JOIN posts ON hit_daily.post_id = posts.id
       WHERE date >= today - days
       GROUP BY hit_daily.post_id, posts.title
       ORDER BY hits DESC LIMIT 50.
       Plus today's contribution from hit_events GROUP BY post_id."""

async def per_tag(s, *, days: int) -> list[TagHits]
    """Same idea but JOIN posts → tags and GROUP BY tag_id."""
```

The "today live" union is consistent across all read methods — never query stale hit_daily for the current UTC day.

`days` is clamped to `[1, 365]` at the route layer.

`per_post` / `per_tag` `LIMIT 50` to bound payload size. Pagination beyond 50 is YAGNI for a personal blog.

## 7. Admin HTTP endpoints

`app/routers/admin/analytics.py`, all require `current_admin`. No `require_scope("write")` since they're read-only.

### 7.1 `GET /api/admin/dashboard`

Response:
```json
{
  "hits": {"today": 142, "last_7d": 980, "last_30d": 3502},
  "likes": {"total": 67, "last_7d": 4},
  "comments": {"total": 32, "pending": 1},
  "posts": {"published": 21, "draft": 3, "scheduled": 1},
  "media": {"count": 18}
}
```

The like/comment/post/media counts come from existing tables via simple aggregation queries (no migration impact).

### 7.2 `GET /api/admin/analytics?days=30`

Response:
```json
{
  "timeseries": [{"date": "2026-04-01", "hits": 89}, ...],
  "top_paths":     [{"path": "/post/foo", "hits": 312}, ...],
  "top_referrers": [{"referrer": "https://news.ycombinator.com/", "hits": 87}, ...],
  "top_countries": [{"country": "US", "hits": 401}, ...]
}
```

`days` clamp `[1, 365]`. Each top-N list has `limit = 10` (hardcoded).

### 7.3 `GET /api/admin/analytics/posts?days=30`

Response: `[{post_id: str, title: str, hits: int}, ...]`, sorted by hits DESC, max 50.

### 7.4 `GET /api/admin/analytics/tags?days=30`

Response: `[{tag_id: int, slug: str, name: str, hits: int}, ...]`, sorted by hits DESC. No limit (tag count is small).

## 8. Pydantic schemas

`app/schemas/analytics.py`:

```python
class HitRequest(BaseModel):
    path: str = Field(max_length=512)
    referrer: str | None = Field(default=None, max_length=512)
    post_id: str | None = Field(default=None, max_length=64)

class HitsKPI(BaseModel):
    today: int
    last_7d: int
    last_30d: int

class LikesKPI(BaseModel):
    total: int
    last_7d: int

class CommentsKPI(BaseModel):
    total: int
    pending: int

class PostsKPI(BaseModel):
    published: int
    draft: int
    scheduled: int

class MediaKPI(BaseModel):
    count: int

class DashboardResponse(BaseModel):
    hits: HitsKPI
    likes: LikesKPI
    comments: CommentsKPI
    posts: PostsKPI
    media: MediaKPI

class DayPoint(BaseModel):
    date: date
    hits: int

class PathHits(BaseModel):
    path: str
    hits: int

class ReferrerHits(BaseModel):
    referrer: str
    hits: int

class CountryHits(BaseModel):
    country: str
    hits: int

class AnalyticsBundleResponse(BaseModel):
    timeseries: list[DayPoint]
    top_paths: list[PathHits]
    top_referrers: list[ReferrerHits]
    top_countries: list[CountryHits]

class PostHitsItem(BaseModel):
    post_id: str
    title: str
    hits: int

class TagHitsItem(BaseModel):
    tag_id: int
    slug: str
    name: str
    hits: int
```

## 9. Event log

Two new event types:

- `analytics.rollup` — actor=system, target=str(date), meta={date, paths_rolled, rows_truncated}
- `analytics.rollup_failed` — actor=system, target=str(date), meta={date, error}

`POST /api/hit` itself does NOT write event_log (volume too high).

## 10. Test plan

### 10.1 Unit — `tests/test_hits_service.py` (~10 tests)

- `record` happy path: insert + Redis key set.
- `record` UA matches BOT_RE → returns False, no insert.
- `record` second call within 60s with same (ip, path) → False.
- `record` different path same IP → both pass.
- `record` `post_id` not in posts → row written with post_id NULL.
- `record` country lower-case "us" → NULL (validation requires uppercase per spec).
- `record` country non-ISO ("USA"/"u1"/"") → NULL.
- `record` IP empty string → still de-dups via "" key (no crash).
- `record` 61s after first call (advance Redis TTL) → True (dedup expired).

### 10.2 Unit — `tests/test_analytics_service.py` (~8 tests)

- `timeseries(days=7)` returns 7 items including 0-padded days.
- `top_paths` ordered DESC + limit honored.
- `dashboard_kpis().hits.today` reads hit_events not hit_daily.
- `dashboard_kpis().posts` counts come from `posts.status` correctly.
- `per_post` joins to posts.title; missing post (post_id NULL) excluded.
- `per_tag` JOINs posts → tags, GROUP BY tag_id.
- `top_referrers` merges JSONB arrays from N hit_daily rows correctly.

### 10.3 HTTP — `tests/test_public_hits.py` (~6 tests)

- POST /api/hit valid body → 204 + 1 row in hit_events.
- POST /api/hit missing path → 422.
- POST /api/hit twice same IP+path → both 204; only 1 row.
- POST /api/hit non-existent post_id → 204; row.post_id IS NULL.
- POST /api/hit User-Agent="GoogleBot/2.1" → 204; 0 rows.
- POST /api/hit `CF-IPCountry: JP` → row.country == "JP".

### 10.4 HTTP — `tests/test_admin_analytics.py` (~10 tests)

- 4 endpoints all 401 without bearer.
- `/api/admin/dashboard` counts match seeded fixtures (likes from P4, comments from P4, posts from P3, media from P6a, hits from this phase).
- `/api/admin/analytics?days=7` returns 7-day timeseries + top arrays.
- `days=0` → 422 (Pydantic validation).
- `days=10000` → clamped to 365.
- `days=-1` → 422.
- `/api/admin/analytics/posts?days=30` ORDER BY hits DESC; title joined.
- `/api/admin/analytics/tags?days=30` JOIN to tags correct.
- DELETE post → that post no longer appears in `/analytics/posts` (FK SET NULL → filtered).
- Empty DB → all 4 endpoints return 200 with zero/empty values.

### 10.5 ARQ rollup — `tests/test_analytics_rollup.py` (~5 tests)

Run with `ARQ_INLINE=true`:

- Seed 5 events for path A yesterday + 3 events for path B yesterday + 2 events 31 days old. Run task with `target_date=yesterday`. Assert: 2 hit_daily rows; A.hits=5, B.hits=3; 31-day-old raws gone; recent raws preserved.
- referrers_top JSON contains correct top entries with counts.
- countries_top JSON respects NULL country (excluded from top).
- Idempotent: run task twice → hit_daily not duplicated, hits unchanged.
- Empty hit_events for the day → task succeeds; returns paths_rolled=0, rows_truncated counts older raws.

### 10.6 Migration — `tests/test_alembic_0006_roundtrip.py`

Same subprocess pattern as 0005's round-trip:

```
alembic downgrade 0005_media → alembic upgrade head → alembic current == 0006_analytics
```

### 10.7 Acceptance criteria

- [ ] `hit_events` + `hit_daily` tables created via 0006_analytics; round-trip clean.
- [ ] `POST /api/hit` returns 204 always (accepted/filtered indistinguishable).
- [ ] Beacon flow: bot UA dropped, 60s dedup honored.
- [ ] Country populates from `CF-IPCountry` header; NULL otherwise.
- [ ] `post_id` validated; non-existent slug → NULL row.
- [ ] ARQ `analytics_rollup_task` rolls a UTC day's hits → hit_daily; idempotent.
- [ ] Raw hit_events older than 30 days are truncated by the task.
- [ ] `analytics.rollup` event_log fires after each task run.
- [ ] 4 admin endpoints all require auth; return correct counts.
- [ ] `/admin/analytics/posts` and `/admin/analytics/tags` correctly join via post_id FK.
- [ ] All P3/P4/P5/P6a tests still pass (298 baseline + ~40 new ≈ ~338).

## 11. Implementation order

Sketch (writing-plans authors detailed TDD steps):

1. Migration 0006 + ORM models for HitEvent + HitDaily.
2. Pydantic schemas (request + response).
3. `hits` service with record() + filters (TDD: bot, dedup, country, post_id).
4. `POST /api/hit` route + Pydantic validation.
5. `analytics_rollup_task` ARQ task + cron registration.
6. `analytics` read service (dashboard_kpis, timeseries, top_*, per_post, per_tag).
7. Admin router (4 endpoints).
8. Event_log wiring (analytics.rollup / rollup_failed).
9. Migration round-trip test.
10. Manual smoke: curl beacon, advance time mocked, run task, GET admin endpoints.

## 12. Backwards-compat

- `posts` / `tags` / `like_events` / `comments` / `media` schemas untouched.
- `event_log` gets two new types but the table is unchanged.
- ARQ worker keeps existing tasks (`send_email_task` from P5); we add one cron + one task definition.
- 0 P3/P4/P5/P6a-introduced ruff errors maintained.
