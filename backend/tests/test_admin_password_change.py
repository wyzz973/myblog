"""POST /api/admin/account/password tests."""
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
async def restore_password():
    """Reset admin password to the canonical fixture value at teardown."""
    yield
    from app.cli import _seed_admin
    await _seed_admin(EMAIL, PASS)


@pytest.fixture
async def admin_token(client):
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    assert r.status_code == 200, r.text
    return r.json()["access"]


async def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_change_password_requires_token(client):
    r = await client.post(
        "/api/admin/account/password",
        json={"current_password": PASS, "new_password": "newvalid123"},
    )
    assert r.status_code == 401


async def test_change_password_wrong_current_400(client, admin_token):
    r = await client.post(
        "/api/admin/account/password",
        json={"current_password": "wrong-pw", "new_password": "newvalid123"},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()


async def test_change_password_same_as_current_400(client, admin_token):
    r = await client.post(
        "/api/admin/account/password",
        json={"current_password": PASS, "new_password": PASS},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 400


async def test_change_password_too_short_422(client, admin_token):
    r = await client.post(
        "/api/admin/account/password",
        json={"current_password": PASS, "new_password": "short"},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 422


async def test_change_password_succeeds_and_old_password_stops_working(
    client, admin_token, restore_password
):
    new_pw = "rotated-pw-456"
    r = await client.post(
        "/api/admin/account/password",
        json={"current_password": PASS, "new_password": new_pw},
        headers=await _auth(admin_token),
    )
    assert r.status_code == 204

    # New password works.
    r2 = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": new_pw}
    )
    assert r2.status_code == 200

    # Old password no longer works.
    r3 = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    assert r3.status_code == 401
