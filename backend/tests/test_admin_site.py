import pytest


@pytest.fixture
async def auth(client):
    r = await client.post(
        "/api/admin/auth/login",
        json={"email": "hi@wangyang.dev", "password": "changeme"},
    )
    return {"Authorization": f"Bearer {r.json()['access']}"}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


async def test_profile_get_and_put(client, auth):
    g = await client.get("/api/admin/profile", headers=auth)
    assert g.status_code == 200
    body = g.json()
    # All ProfileIn fields exposed in response
    for k in ("name", "name_en", "role", "bio", "location", "pronouns",
              "avatar_path", "typing_line", "stack_chips"):
        assert k in body

    p = await client.put(
        "/api/admin/profile",
        json={"role": "Backend / AI / Tinkerer"},
        headers=auth,
    )
    assert p.status_code == 200
    assert p.json()["role"] == "Backend / AI / Tinkerer"


async def test_profile_put_requires_auth(client):
    r = await client.put("/api/admin/profile", json={"role": "x"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------


async def test_site_get_and_put_partial(client, auth):
    g = await client.get("/api/admin/site", headers=auth)
    assert g.status_code == 200
    for k in ("handle", "tagline", "email", "github", "footer_note",
              "default_theme", "launched_at"):
        assert k in g.json()

    p = await client.put(
        "/api/admin/site", json={"footer_note": "© 2026 wy"}, headers=auth
    )
    assert p.status_code == 200
    assert p.json()["footer_note"] == "© 2026 wy"


async def test_site_put_launched_at_iso(client, auth):
    p = await client.put(
        "/api/admin/site", json={"launched_at": "2024-06-15"}, headers=auth
    )
    assert p.status_code == 200
    assert p.json()["launched_at"] == "2024-06-15"


async def test_site_put_launched_at_invalid(client, auth):
    p = await client.put(
        "/api/admin/site", json={"launched_at": "not-a-date"}, headers=auth
    )
    assert p.status_code == 422


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


async def test_theme_put_color(client, auth):
    p = await client.put(
        "/api/admin/theme",
        json={"accent_color": "oklch(85% 0.18 152)"},
        headers=auth,
    )
    assert p.status_code == 200
    assert p.json()["accent_color"].startswith("oklch")


async def test_theme_get_returns_all_colors(client, auth):
    g = await client.get("/api/admin/theme", headers=auth)
    assert g.status_code == 200
    body = g.json()
    for k in ("accent_color", "accent2_color", "violet_color", "danger_color"):
        assert k in body
