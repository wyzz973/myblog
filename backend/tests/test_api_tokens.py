import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def cleanup_tokens():
    yield
    from sqlalchemy import delete
    from app.db import AsyncSessionLocal
    from app.models import ApiToken
    async with AsyncSessionLocal() as s:
        await s.execute(delete(ApiToken))
        await s.commit()


async def test_create_returns_raw_once(client, admin_token, cleanup_tokens):
    r = await client.post(
        "/api/admin/api-tokens",
        json={"name": "ci", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "ci"
    assert body["scope"] == "write"
    assert body["token"].startswith("tk_")
    assert len(body["token"]) >= 36


async def test_list_hides_hash(client, admin_token, cleanup_tokens):
    await client.post(
        "/api/admin/api-tokens",
        json={"name": "a", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.get(
        "/api/admin/api-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert "token" not in items[0]
    assert "token_hash" not in items[0]


async def test_delete_marks_revoked(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "x", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = create.json()["id"]
    r = await client.delete(
        f"/api/admin/api-tokens/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    listing = await client.get(
        "/api/admin/api-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listing.json()[0]["revoked_at"] is not None


async def test_invalid_scope_rejected(client, admin_token, cleanup_tokens):
    r = await client.post(
        "/api/admin/api-tokens",
        json={"name": "z", "scope": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_read_token_can_get_admin_posts(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "r", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    r = await client.get("/api/admin/posts", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200


async def test_read_token_cannot_post_admin(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "r", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    r = await client.post(
        "/api/admin/tags",
        json={"slug": "should-fail", "name": "x", "color": "#fff"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403


async def test_write_token_can_post(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "w", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    r = await client.post(
        "/api/admin/tags",
        json={"slug": "wtoken-tag", "name": "w-tag", "color": "#aaa"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code in (200, 201)
    # cleanup
    from sqlalchemy import delete
    from app.db import AsyncSessionLocal
    from app.models import Tag
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Tag).where(Tag.slug == "wtoken-tag"))
        await s.commit()


async def test_revoked_token_rejected(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "rev", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    tid = create.json()["id"]
    await client.delete(
        f"/api/admin/api-tokens/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.get("/api/admin/posts", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


async def test_session_only_endpoint_rejects_token(client, admin_token, cleanup_tokens):
    """API tokens must NOT be allowed to manage their own scope tier."""
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "self", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    # /account/2fa/setup is session-only
    r = await client.post(
        "/api/admin/account/2fa/setup", headers={"Authorization": f"Bearer {raw}"}
    )
    assert r.status_code == 401
