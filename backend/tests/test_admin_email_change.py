"""POST /api/admin/account/email tests (Task 28a)."""
import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def restore_email():
    """Restore admin.email to the canonical fixture value at teardown."""
    yield
    from sqlalchemy import update
    from app.db import AsyncSessionLocal
    from app.models import Account
    async with AsyncSessionLocal() as s:
        await s.execute(update(Account).where(Account.id == 1).values(email=EMAIL))
        await s.commit()


@pytest.fixture
async def admin_token(client):
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    assert r.status_code == 200, r.text
    return r.json()["access"]


async def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_change_email_requires_session(client):
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": PASS, "new_email": "new@example.com"},
    )
    assert r.status_code == 401


async def test_change_email_happy_path(client, admin_token, restore_email):
    new = "rotated@example.com"
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": PASS, "new_email": new},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == new
    # Login under the new email succeeds
    r2 = await client.post(
        "/api/admin/auth/login", json={"email": new, "password": PASS}
    )
    assert r2.status_code == 200, r2.text
    # Old email no longer authenticates
    r3 = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    assert r3.status_code == 401


async def test_change_email_wrong_password(client, admin_token, restore_email):
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": "not-it", "new_email": "x@example.com"},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 400
    assert "password" in r.json()["detail"].lower()


async def test_change_email_same_email_rejected(client, admin_token, restore_email):
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": PASS, "new_email": EMAIL},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 400
    assert "differ" in r.json()["detail"].lower()


async def test_change_email_invalid_address_422(client, admin_token, restore_email):
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": PASS, "new_email": "not-an-email"},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 422


async def test_change_email_writes_event_log(client, admin_token, restore_email):
    new = "logged@example.com"
    r = await client.post(
        "/api/admin/account/email",
        json={"current_password": PASS, "new_email": new},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 200

    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import EventLog
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(EventLog)
                .where(EventLog.type == "account.email.changed")
                .order_by(EventLog.created_at.desc())
                .limit(1)
            )
        ).scalars().all()
    assert rows, "no event log row for account.email.changed"
    meta = rows[0].meta
    assert meta["old"] == EMAIL
    assert meta["new"] == new


async def test_change_email_rejects_api_token(client, admin_token, restore_email):
    """Email change is session-only; api-tokens cannot rotate the email."""
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t28a", "scope": "write"},
        headers=await _auth(admin_token),
    )
    assert create.status_code == 200
    raw = create.json()["token"]
    try:
        r = await client.post(
            "/api/admin/account/email",
            json={"current_password": PASS, "new_email": "x@example.com"},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 401
    finally:
        from sqlalchemy import delete
        from app.db import AsyncSessionLocal
        from app.models import ApiToken
        async with AsyncSessionLocal() as s:
            await s.execute(delete(ApiToken))
            await s.commit()
