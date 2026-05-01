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
    assert "per_ip_per_min" in body
    assert isinstance(body["fallback_lines"], list)
    assert len(body["fallback_lines"]) >= 1


async def test_pet_put_replaces_config(client, admin_token):
    new_config = {
        "system_prompt": "You are very brief.",
        "fallback_lines": ["a", "b", "c"],
        "tired_lines": ["napping..."],
        "per_ip_per_min": 4,
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
    config = {"fallback_lines": [], "system_prompt": "x",
              "per_ip_per_min": 6, "enabled": True, "species": "cat",
              "hat": "none", "tint": "#000", "visitor_can_change": False}
    r = await client.put(
        "/api/admin/pet", json=config,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


@pytest.mark.xfail(reason="species is now a free-form str (Literal constraint removed in Task 3 schema refactor)")
async def test_pet_put_invalid_species_rejected(client, admin_token):
    config = {"system_prompt": "x", "fallback_lines": ["a"],
              "per_ip_per_min": 6, "enabled": True, "species": "dragon",
              "hat": "none", "tint": "#000", "visitor_can_change": False}
    r = await client.put(
        "/api/admin/pet", json=config,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_petconfig_defaults_include_new_fields(client, admin_token):
    r = await client.get("/api/admin/pet", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    j = r.json()
    assert j["providers"] == ["zhipu"]
    assert j["per_ip_per_min"] == 6
    assert j["per_ip_per_day"] == 30
    assert j["global_per_day"] == 500
    assert j["max_context_chars"] == 500
    assert j["enable_article_context"] is True
    assert isinstance(j["tired_lines"], list) and len(j["tired_lines"]) >= 1


async def test_petconfig_rejects_unknown_provider(client, admin_token):
    body = {
        "providers": ["openai"],  # not in registry
        "fallback_lines": ["x"],
        "tired_lines": ["y"],
    }
    r = await client.put("/api/admin/pet", headers={"Authorization": f"Bearer {admin_token}"}, json=body)
    assert r.status_code == 422
