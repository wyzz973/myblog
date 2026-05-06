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
    tid = create.json()["id"]
    # /account/2fa/setup is session-only
    r = await client.post(
        "/api/admin/account/2fa/setup", headers={"Authorization": f"Bearer {raw}"}
    )
    assert r.status_code == 401

    # Bug fix verification: rejected calls must not tick last_used_at
    from sqlalchemy import select

    from app.db import AsyncSessionLocal
    from app.models import ApiToken
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ApiToken).where(ApiToken.id == tid))).scalar_one()
        assert row.last_used_at is None


# --- Task 29: usage_count counter on api_tokens ---


async def test_list_includes_usage_count(client, admin_token, cleanup_tokens):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create.status_code == 200
    listing = await client.get(
        "/api/admin/api-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = listing.json()
    assert all("usage_count" in t for t in body), body
    # New token has never been used.
    fresh = next(t for t in body if t["name"] == "t29")
    assert fresh["usage_count"] == 0


async def test_usage_count_increments_on_scope_passing_request(
    client, admin_token, cleanup_tokens,
):
    """Counter ticks on each scope-passing token use. Probed via PATCH
    /api/admin/posts (write-scope) since that's where the touch fires
    today. The post doesn't have to exist — the auth + scope check fires
    before the post lookup."""
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-counted", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    md = "---\nid: x\nn: '999'\ntitle: t\ntag: devtools\ndate: 2026-01-01\n---\n\nbody\n"
    for _ in range(3):
        r = await client.patch(
            "/api/admin/posts/does-not-exist-t29",
            json={"markdown": md},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code in (404, 422), r.text

    listing = (await client.get(
        "/api/admin/api-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    row = next(t for t in listing if t["name"] == "t29-counted")
    assert row["usage_count"] == 3, listing
    assert row["last_used_at"] is not None


async def test_usage_count_not_bumped_on_invalid_token(
    client, admin_token, cleanup_tokens,
):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-rejected", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    bad = raw[:-1] + ("A" if raw[-1] != "A" else "B")
    md = "---\nid: x\nn: '999'\ntitle: t\ntag: devtools\ndate: 2026-01-01\n---\n\nbody\n"
    r = await client.patch(
        "/api/admin/posts/does-not-exist-t29",
        json={"markdown": md},
        headers={"Authorization": f"Bearer {bad}"},
    )
    assert r.status_code == 401
    listing = (await client.get(
        "/api/admin/api-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    row = next(t for t in listing if t["name"] == "t29-rejected")
    assert row["usage_count"] == 0


# --- Task 29: per-request usage log table ---


async def test_usage_endpoint_unknown_token_404(client, admin_token):
    r = await client.get(
        "/api/admin/api-tokens/999999/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_usage_endpoint_empty_for_unused_token(
    client, admin_token, cleanup_tokens,
):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-log-empty", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = create.json()["id"]
    r = await client.get(
        f"/api/admin/api-tokens/{tid}/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


async def test_usage_endpoint_records_each_scope_passing_call(
    client, admin_token, cleanup_tokens,
):
    """Each write-scoped touch path should log one row with method+path.

    The session admin querying /usage shouldn't add to the trail (sessions
    don't tick the counter or insert a usage row); only token-bearing
    requests do.
    """
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-log-fill", "scope": "write"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    tid = create.json()["id"]

    # Two scope-passing calls (creating tags) under the token.
    from sqlalchemy import delete
    from app.db import AsyncSessionLocal
    from app.models import Tag
    try:
        for slug in ("t29-log-1", "t29-log-2"):
            r = await client.post(
                "/api/admin/tags",
                json={"slug": slug, "name": slug, "color": "#888"},
                headers={"Authorization": f"Bearer {raw}"},
            )
            assert r.status_code in (200, 201), r.text

        usage = await client.get(
            f"/api/admin/api-tokens/{tid}/usage",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert usage.status_code == 200, usage.text
        rows = usage.json()
        assert len(rows) == 2, rows
        # Most-recent first; both POST /api/admin/tags
        for r0 in rows:
            assert r0["method"] == "POST"
            assert r0["path"] == "/api/admin/tags"
            assert r0["used_at"]  # ISO timestamp present
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Tag).where(Tag.slug.in_(["t29-log-1", "t29-log-2"])))
            await s.commit()


async def test_usage_endpoint_does_not_log_session_caller(
    client, admin_token, cleanup_tokens,
):
    """Querying /usage with a session JWT must not add to the target token's trail."""
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-no-self-log", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = create.json()["id"]
    raw = create.json()["token"]

    # First make one token-side call to seed the trail.
    await client.get("/api/admin/posts", headers={"Authorization": f"Bearer {raw}"})

    before = (await client.get(
        f"/api/admin/api-tokens/{tid}/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    # Hit the usage endpoint a couple more times *as the admin session*.
    for _ in range(3):
        await client.get(
            f"/api/admin/api-tokens/{tid}/usage",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    after = (await client.get(
        f"/api/admin/api-tokens/{tid}/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )).json()
    # Trail length unchanged: session admin doesn't write to api_token_usage.
    # Note: GET /api/admin/posts under a read-scoped token does NOT pass through
    # require_scope (the posts list endpoint isn't scope-checked in this
    # codebase), so even the seeding hit doesn't write — and the trail stays
    # empty. We assert "monotonic" rather than a specific count to keep the
    # test robust to future changes.
    assert len(after) == len(before)


async def test_usage_endpoint_token_can_view_its_own_trail(
    client, admin_token, cleanup_tokens,
):
    """Read-scoped tokens can query their own usage list (it's a read endpoint).

    Helps owners audit a script's own activity without a session login.
    """
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t29-self-read", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    tid = create.json()["id"]
    r = await client.get(
        f"/api/admin/api-tokens/{tid}/usage",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 200, r.text
