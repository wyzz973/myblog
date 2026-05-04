import pytest

from app.services.pet_assignment import SPECIES_BY_RARITY

EXPECTED_TEMPLATES = {
    "greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa",
    "free_chat", "follow_up", "article_finished", "reading_assist", "code_assist",
    "recommend_next", "pet_care",
}

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_get_defaults_returns_personas_and_templates(client, admin_token):
    r = await client.get("/api/admin/pet/defaults", headers=_hdr(admin_token))
    assert r.status_code == 200
    body = r.json()
    expected_species = {s for pool in SPECIES_BY_RARITY.values() for s in pool}
    assert set(body["personas"]) == expected_species
    assert set(body["mode_templates"]) == EXPECTED_TEMPLATES


async def test_reset_personas_section(client, admin_token):
    # First, mutate cat persona via PUT
    cur = (await client.get("/api/admin/pet", headers=_hdr(admin_token))).json()
    cur["personas"]["cat"] = "MUT"
    await client.put("/api/admin/pet", json=cur, headers=_hdr(admin_token))
    after_mut = (await client.get("/api/admin/pet", headers=_hdr(admin_token))).json()
    assert after_mut["personas"]["cat"] == "MUT"
    # Reset only personas
    r = await client.post("/api/admin/pet/reset?section=personas", headers=_hdr(admin_token))
    assert r.status_code == 200
    after = r.json()
    assert after["personas"]["cat"] != "MUT"
    # Templates not touched
    assert after["mode_templates"] == after_mut["mode_templates"]


async def test_reset_templates_section(client, admin_token):
    cur = (await client.get("/api/admin/pet", headers=_hdr(admin_token))).json()
    cur["mode_templates"]["greet"] = "MUT"
    await client.put("/api/admin/pet", json=cur, headers=_hdr(admin_token))
    after = (await client.post("/api/admin/pet/reset?section=templates", headers=_hdr(admin_token))).json()
    assert "MUT" not in after["mode_templates"]["greet"]


async def test_reset_both_section(client, admin_token):
    cur = (await client.get("/api/admin/pet", headers=_hdr(admin_token))).json()
    cur["personas"]["cat"] = "M1"
    cur["mode_templates"]["greet"] = "M2"
    await client.put("/api/admin/pet", json=cur, headers=_hdr(admin_token))
    after = (await client.post("/api/admin/pet/reset?section=both", headers=_hdr(admin_token))).json()
    assert "M1" not in after["personas"]["cat"]
    assert "M2" not in after["mode_templates"]["greet"]


async def test_reset_invalid_section_returns_422(client, admin_token):
    r = await client.post("/api/admin/pet/reset?section=garbage", headers=_hdr(admin_token))
    assert r.status_code == 422


async def test_reset_personas_preserves_other_fields(client, admin_token):
    """The reset endpoint must only touch its named section. All other
    PetConfig fields (rate-limit, providers, system_prompt, etc.) survive."""
    cur = (await client.get("/api/admin/pet", headers=_hdr(admin_token))).json()
    cur["per_ip_per_min"] = 42
    cur["providers"] = ["zhipu", "qwen"]
    cur["personas"]["cat"] = "MUT"
    await client.put("/api/admin/pet", json=cur, headers=_hdr(admin_token))
    after = (await client.post("/api/admin/pet/reset?section=personas",
                                headers=_hdr(admin_token))).json()
    assert after["per_ip_per_min"] == 42
    assert after["providers"] == ["zhipu", "qwen"]
    assert after["personas"]["cat"] != "MUT"
