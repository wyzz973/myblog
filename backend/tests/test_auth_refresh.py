import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"
COOKIE = "myblog_refresh"


async def _login(client) -> tuple[str, str]:
    """Returns (access, refresh_cookie_value)."""
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, r.text
    return r.json()["access"], r.cookies.get(COOKIE)


async def test_login_sets_refresh_cookie(client):
    _, refresh = await _login(client)
    assert refresh and len(refresh) >= 32


async def test_refresh_rotates_token(client):
    _, refresh = await _login(client)
    r = await client.post("/api/admin/auth/refresh", cookies={COOKIE: refresh})
    assert r.status_code == 200, r.text
    new_refresh = r.cookies.get(COOKIE)
    assert new_refresh and new_refresh != refresh
    assert "access" in r.json()


async def test_refresh_old_token_rejected_after_rotation(client):
    _, refresh = await _login(client)
    r = await client.post("/api/admin/auth/refresh", cookies={COOKIE: refresh})
    assert r.status_code == 200
    # try old refresh again
    r2 = await client.post("/api/admin/auth/refresh", cookies={COOKIE: refresh})
    assert r2.status_code == 401


async def test_refresh_missing_cookie_401(client):
    r = await client.post("/api/admin/auth/refresh")
    assert r.status_code == 401


async def test_logout_kills_refresh(client):
    _, refresh = await _login(client)
    r = await client.post("/api/admin/auth/logout", cookies={COOKIE: refresh})
    assert r.status_code == 204
    r2 = await client.post("/api/admin/auth/refresh", cookies={COOKIE: refresh})
    assert r2.status_code == 401
