"""Site content wipe service: TRUNCATE content tables, reset site_meta to
CLI seed defaults, unlink media files. Preserves admin login + audit trail."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comment,
    Contact,
    ContribDay,
    HitDaily,
    HitEvent,
    Integration,
    LikeEvent,
    Media,
    NowEntry,
    Post,
    Project,
    SiteMeta,
    Tag,
)
from app.services import media_storage


# Order matters: child tables before their parents to satisfy FK constraints.
# Posts has FK to tags → wipe Posts before Tags.
# Comments / Likes have FK to posts → wipe before posts.
# HitEvents / HitDaily have FK to posts → wipe before posts.
# Media has no inbound FK from content; site_meta.avatar_id is NULL'd via
#   ON DELETE SET NULL when we wipe Media.
WIPE_ORDER = [
    HitEvent, HitDaily, LikeEvent, Comment,
    Post, Tag,                   # Post → Tag FK
    Project, Contact, NowEntry, ContribDay,
    Integration,
    Media,                       # ON DELETE SET NULL fires for site_meta.avatar_id
]


SITE_META_DEFAULTS = {
    "handle": "wangyang",
    "name": "汪洋",
    "name_en": "Wang Yang",
    "role": "Backend / AI Full-Stack Engineer",
    "tagline": "Backends that don't flinch. Models that ship.",
    "bio": "I build backend systems and AI agents.",
    "location": "Hangzhou, CN",
    "email": "hi@wangyang.dev",
    "github": "wangyang",
    "pronouns": None,
    "avatar_path": None,
    "avatar_id": None,
    "typing_line": (
        "// building backends that don't flinch.\n// training models that ship."
    ),
    "stack_chips": ["Java", "Python", "PyTorch", "Agents", "Segmentation"],
    "footer_note": "© 2026 Wang Yang · hand-coded · cookie-less analytics",
    "default_theme": "dark",
    "accent_color": "oklch(82% 0.17 152)",
    "accent2_color": "oklch(80% 0.15 70)",
    "violet_color": "oklch(72% 0.18 295)",
    "danger_color": "oklch(70% 0.2 25)",
    "launched_at": date(2023, 1, 1),
    "pet_config": {},
    "pending_delete_at": None,
}


async def wipe_site_content(s: AsyncSession) -> dict:
    """TRUNCATE content tables + reset site_meta to defaults + unlink media files.
    Returns {tables_wiped, rows_destroyed_total}.

    Order of operations:
      1. Walk Media rows: unlink each file under data/media/ (idempotent if missing).
      2. DELETE all WIPE_ORDER tables in FK-safe order.
      3. UPDATE site_meta SET ... = defaults WHERE id = 1.
    """
    # Step 1: unlink media files first.
    media_rows = (await s.execute(select(Media))).scalars().all()
    for m in media_rows:
        try:
            await media_storage.delete(m.storage_path)
        except Exception:
            pass  # idempotent — missing files are fine

    # Step 2: TRUNCATE content tables.
    rows_destroyed = 0
    tables_wiped = 0
    for model in WIPE_ORDER:
        res = await s.execute(delete(model))
        rows_destroyed += res.rowcount or 0
        tables_wiped += 1

    # Step 3: reset site_meta to defaults.
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(**SITE_META_DEFAULTS)
    )
    await s.flush()
    return {"tables_wiped": tables_wiped, "rows_destroyed_total": rows_destroyed}
