import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


async def test_pet_get_returns_defaults(client, admin_token):
    r = await client.get(
        "/api/admin/pet",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "model" in body
    assert isinstance(body["fallback_lines"], list)
    assert len(body["fallback_lines"]) >= 1


async def test_pet_put_replaces_config(client, admin_token):
    new_config = {
        "model": "claude-haiku-4-5-20251001",
        "system_prompt": "You are very brief.",
        "fallback_lines": ["a", "b", "c"],
        "rate_limit_per_min": 4,
        "enabled": True,
        "species": "fox",
        "hat": "wizard",
        "tint": "#ff6677",
        "visitor_can_change": False,
    }
    r = await client.put(
        "/api/admin/pet", json=new_config,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["species"] == "fox"
    assert body["fallback_lines"] == ["a", "b", "c"]


async def test_pet_put_empty_fallback_lines_rejected(client, admin_token):
    config = {"fallback_lines": [], "model": "x", "system_prompt": "x",
              "rate_limit_per_min": 6, "enabled": True, "species": "cat",
              "hat": "none", "tint": "#000", "visitor_can_change": False}
    r = await client.put(
        "/api/admin/pet", json=config,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_pet_put_invalid_species_rejected(client, admin_token):
    config = {"model": "x", "system_prompt": "x", "fallback_lines": ["a"],
              "rate_limit_per_min": 6, "enabled": True, "species": "dragon",
              "hat": "none", "tint": "#000", "visitor_can_change": False}
    r = await client.put(
        "/api/admin/pet", json=config,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422
