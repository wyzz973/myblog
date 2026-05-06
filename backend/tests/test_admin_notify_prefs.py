"""Task 43: comment notification preferences endpoints."""
import pytest

from sqlalchemy import update
from app.db import AsyncSessionLocal
from app.models import Account


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


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
async def restore_notify_prefs():
    """Reset account.notify_comments=True / notify_email=NULL after each test."""
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Account)
            .where(Account.id == 1)
            .values(notify_comments=True, notify_email=None)
        )
        await s.commit()


async def test_get_returns_defaults(client, admin_token, restore_notify_prefs):
    r = await client.get("/api/admin/account/notify", headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notify_comments"] is True
    assert body["notify_email"] is None
    # effective_email falls back through settings.admin_notify_email or login email
    assert body["effective_email"]  # something resolved


async def test_put_sets_override_address(client, admin_token, restore_notify_prefs):
    r = await client.put(
        "/api/admin/account/notify",
        json={"notify_comments": True, "notify_email": "owner@example.com"},
        headers={**_hdr(admin_token), "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notify_comments"] is True
    assert body["notify_email"] == "owner@example.com"
    # Override takes priority — effective MUST equal the override.
    assert body["effective_email"] == "owner@example.com"


async def test_put_master_off_clears_effective(
    client, admin_token, restore_notify_prefs,
):
    r = await client.put(
        "/api/admin/account/notify",
        json={"notify_comments": False, "notify_email": "owner@example.com"},
        headers={**_hdr(admin_token), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["effective_email"] is None  # opt-out wins


async def test_put_clears_override(client, admin_token, restore_notify_prefs):
    """Empty notify_email round-trip: set then null again."""
    await client.put(
        "/api/admin/account/notify",
        json={"notify_comments": True, "notify_email": "owner@example.com"},
        headers={**_hdr(admin_token), "Content-Type": "application/json"},
    )
    r = await client.put(
        "/api/admin/account/notify",
        json={"notify_comments": True, "notify_email": None},
        headers={**_hdr(admin_token), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["notify_email"] is None


async def test_get_requires_session(client):
    r = await client.get("/api/admin/account/notify")
    assert r.status_code == 401


async def test_session_only_rejects_api_token(
    client, admin_token, restore_notify_prefs,
):
    """Notification prefs are session-only (like password change)."""
    cr = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t43-tok", "scope": "write"},
        headers=_hdr(admin_token),
    )
    raw = cr.json()["token"]
    try:
        r = await client.get(
            "/api/admin/account/notify",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 401
    finally:
        from sqlalchemy import delete
        from app.models import ApiToken
        async with AsyncSessionLocal() as s:
            await s.execute(delete(ApiToken))
            await s.commit()
