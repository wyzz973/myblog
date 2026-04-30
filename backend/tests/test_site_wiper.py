"""site_wiper service unit tests."""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from app.db import AsyncSessionLocal
from app.models import (
    Account,
    Comment,
    Contact,
    ContribDay,
    EventLog,
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
from app.services import site_wiper


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seeded_site(tmp_path, monkeypatch):
    """Seed a few rows into every wipe-target table + a media file on disk.
    Yields the tmp_path used as MEDIA_DIR."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)

    # Seed minimal rows. We rely on the existing CLI bootstrap so admin and
    # site_meta already exist.
    async with AsyncSessionLocal() as s:
        # Get an existing tag so we can FK posts to it; create one if a prior
        # wipe in the test session removed all of them.
        tag = (await s.execute(select(Tag).limit(1))).scalar_one_or_none()
        if tag is None:
            tag = Tag(slug="wipetest-tag", name="WipeTest", color="#7dd3a4",
                      sort_order=0)
            s.add(tag)
            await s.flush()
        # post (flush so subsequent FK references can find it)
        s.add(Post(
            id="wipetest", n="9", title="W", subtitle="", date=datetime.now(UTC).date(),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=tag.id,
        ))
        await s.flush()
        # contact
        s.add(Contact(label="x", value="x@x.com", href="mailto:x@x.com",
                      visible=True, sort_order=0))
        # now entry
        s.add(NowEntry(body_md="hi", listening="", reading="",
                       is_current=True, created_at=datetime.now(UTC)))
        # contrib_day — pick a future date that real GitHub-sync data won't touch
        from datetime import timedelta
        s.add(ContribDay(day=datetime.now(UTC).date() + timedelta(days=400), count=3))
        # like
        s.add(LikeEvent(post_id="wipetest", ip_hash="abc",
                        day=datetime.now(UTC).date(), created_at=datetime.now(UTC)))
        # hit
        s.add(HitEvent(path="/", created_at=datetime.now(UTC)))
        s.add(HitDaily(date=datetime.now(UTC).date(), path="/",
                       hits=3, referrers_top=[], countries_top=[]))
        # integration — upsert so a pre-configured prod PAT (if present) is
        # overwritten with a placeholder that the wipe test can verify is
        # deleted, instead of a duplicate-PK error from the fixture.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        await s.execute(
            pg_insert(Integration)
            .values(name="github", secret_encrypted="x", extra_json={},
                    created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
            .on_conflict_do_update(
                index_elements=[Integration.name],
                set_={"secret_encrypted": "x", "extra_json": {}},
            )
        )
        # media file on disk + DB row
        bucket_dir = tmp_path / "aa"
        bucket_dir.mkdir(parents=True, exist_ok=True)
        png = BytesIO()
        Image.new("RGB", (4, 4), "green").save(png, format="PNG")
        media_path = bucket_dir / "wipetest-cat.png"
        media_path.write_bytes(png.getvalue())
        s.add(Media(
            filename="cat.png", storage_path="aa/wipetest-cat.png",
            mime_type="image/png", size=len(png.getvalue()),
            width=4, height=4, alt=None, created_at=datetime.now(UTC),
        ))
        # event_log noise
        s.add(EventLog(type="test.seed", actor="test", target=None, meta={}))
        await s.commit()

    yield tmp_path

    # Re-bootstrap is heavy; tests run wipe and verify, then we re-seed
    # via cli or just leave the empty state. Cleanup just removes leftover
    # rows (idempotent).


async def test_wipe_clears_content_tables(seeded_site, reseed_after):
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()

    async with AsyncSessionLocal() as s:
        for model in (Post, Contact, NowEntry, ContribDay, LikeEvent,
                      HitEvent, HitDaily, Integration, Media, Comment, Tag, Project):
            count = (await s.execute(select(func.count()).select_from(model))).scalar()
            assert count == 0, f"{model.__name__} not wiped: {count} rows"


async def test_wipe_preserves_admin(seeded_site, reseed_after):
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(Account))).scalars().all()
        before_count = len(before)
        before_email = before[0].email if before else None
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(Account))).scalars().all()
    assert len(after) == before_count
    assert after[0].email == before_email


async def test_wipe_resets_site_meta_to_defaults(seeded_site, reseed_after):
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(
            handle="custom", name="Custom", pending_delete_at=datetime.now(UTC)
        ))
        await s.commit()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.handle == "admin"
    assert sm.name == ""
    assert sm.pending_delete_at is None
    assert sm.avatar_id is None


async def test_wipe_preserves_event_log(seeded_site, reseed_after):
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(func.count()).select_from(EventLog))).scalar()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(func.count()).select_from(EventLog))).scalar()
    assert after >= before  # event_log preserved (and may have new rows from the wipe itself)


async def test_wipe_removes_media_files_on_disk(seeded_site, reseed_after):
    media_dir = seeded_site
    f = media_dir / "aa" / "wipetest-cat.png"
    assert f.exists()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    assert not f.exists()
