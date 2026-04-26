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


async def test_login_rate_limit(client, redis):
    for _ in range(5):
        await client.post(
            "/api/admin/auth/login", json={"email": EMAIL, "password": "wrong"}
        )
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": "wrong"}
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


async def test_login_lockout(client, redis):
    # The 5/min throttle would 429 us on call #6 before the 10-fail counter
    # ever ticks to threshold. To assert the *lockout* path specifically,
    # plant the lockout key directly (this is the same key set by
    # mark_failure() once it reaches threshold).
    await redis.set("rl:lock:login:127.0.0.1", "1", ex=900)
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


async def test_2fa_challenge_rate_limit(client, redis):
    # NB: relies on a fresh challenge in Redis with the limiter wired
    # We craft the challenge directly so we don't need 2FA enabled.
    await redis.set("2fa:rate-test", "1", ex=300)
    for _ in range(5):
        await client.post(
            "/api/admin/auth/2fa", json={"challenge": "rate-test", "code": "000000"}
        )
    r = await client.post(
        "/api/admin/auth/2fa", json={"challenge": "rate-test", "code": "000000"}
    )
    assert r.status_code == 429


async def test_magic_link_rate_limit(client, redis):
    for _ in range(3):
        await client.post("/api/admin/auth/magic-link", json={"email": EMAIL})
    r = await client.post("/api/admin/auth/magic-link", json={"email": EMAIL})
    assert r.status_code == 429
