"""Phase 7: avatar_path is derived from avatar_id at site response time.

When ``site_meta.avatar_id`` is set, ``avatar_path`` in serialized site
responses (public ``GET /api/profile`` and admin ``GET /api/admin/profile``)
must be derived from the linked Media row's ``storage_path`` via
``media_storage.url_for``. When ``avatar_id`` is NULL, fall back to the
legacy ``avatar_path`` column.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, update

from app.db import AsyncSessionLocal
from app.models import Media, SiteMeta

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    return r.json()["access"]


@pytest.fixture
async def restore_site_meta():
    """Reset legacy avatar_path + avatar_id after the test so other tests
    see clean SiteMeta state."""
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(SiteMeta)
            .where(SiteMeta.id == 1)
            .values(avatar_id=None, avatar_path=None)
        )
        await s.execute(delete(Media))
        await s.commit()


async def _seed_media(s, *, storage_path: str) -> int:
    row = Media(
        filename="avatar.png",
        storage_path=storage_path,
        mime_type="image/png",
        size=42,
        width=64,
        height=64,
        alt=None,
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    return row.id


async def test_public_profile_avatar_id_none_uses_legacy_column(
    client, restore_site_meta
):
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(SiteMeta)
            .where(SiteMeta.id == 1)
            .values(avatar_id=None, avatar_path="/legacy/old-avatar.png")
        )
        await s.commit()

    r = await client.get("/api/profile")
    assert r.status_code == 200
    assert r.json()["avatar_path"] == "/legacy/old-avatar.png"


async def test_public_profile_avatar_id_set_derives_from_media(
    client, restore_site_meta
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="ab/new-avatar.png")
        await s.execute(
            update(SiteMeta)
            .where(SiteMeta.id == 1)
            .values(avatar_id=mid, avatar_path="/legacy/should-be-ignored.png")
        )
        await s.commit()

    r = await client.get("/api/profile")
    assert r.status_code == 200
    # Derived from media.storage_path → /media/<storage_path>, not the legacy column.
    assert r.json()["avatar_path"] == "/media/ab/new-avatar.png"


async def test_admin_profile_avatar_id_none_uses_legacy_column(
    client, admin_token, restore_site_meta
):
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(SiteMeta)
            .where(SiteMeta.id == 1)
            .values(avatar_id=None, avatar_path="/legacy/admin-old.png")
        )
        await s.commit()

    r = await client.get(
        "/api/admin/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["avatar_path"] == "/legacy/admin-old.png"


async def test_admin_profile_avatar_id_set_derives_from_media(
    client, admin_token, restore_site_meta
):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="cd/admin-avatar.png")
        await s.execute(
            update(SiteMeta)
            .where(SiteMeta.id == 1)
            .values(avatar_id=mid, avatar_path="/legacy/ignored.png")
        )
        await s.commit()

    r = await client.get(
        "/api/admin/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["avatar_path"] == "/media/cd/admin-avatar.png"


async def test_admin_profile_put_response_also_derives(
    client, admin_token, restore_site_meta
):
    """PUT /admin/profile returns the same shape; derivation must apply there too."""
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="ef/put-avatar.png")
        await s.execute(
            update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=mid)
        )
        await s.commit()

    r = await client.put(
        "/api/admin/profile",
        json={"role": "Hacker"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["avatar_path"] == "/media/ef/put-avatar.png"
