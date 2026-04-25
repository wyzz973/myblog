import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, r.text
    return r.json()["access"]


async def test_login_bad_password_401(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": "wrong"})
    assert r.status_code == 401


async def test_login_unknown_email_401(client):
    r = await client.post("/api/admin/auth/login", json={"email": "nobody@x.com", "password": "x"})
    assert r.status_code == 401


async def test_session_requires_token(client):
    r = await client.get("/api/admin/session")
    assert r.status_code == 401


async def test_session_returns_account(client, admin_token):
    r = await client.get("/api/admin/session", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL
