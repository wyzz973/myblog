"""HTTP-level tests for the pet_species CRUD router (Task 21c).

Covers the admin CRUD surface plus the public visible-only read endpoint.
The fixture seed (migration 0016) puts ~27 rows in the table; we add and
remove only ids prefixed with 't21c-' so we don't disturb the catalogue.
"""
import pytest
from sqlalchemy import delete, update

from app.db import AsyncSessionLocal
from app.models import PetSpecies, SiteMeta


EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": PASS}
    )
    assert r.status_code == 200, r.text
    return r.json()["access"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
async def cleanup_t21c():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(PetSpecies).where(PetSpecies.id.like("t21c-%")))
        await s.commit()


# ------------------------------- public list -------------------------------

async def test_public_list_returns_visible_only(client, cleanup_t21c):
    # Add one hidden + one visible row prefixed t21c- so we can verify the
    # filter without depending on which seeded row toggled visibility.
    async with AsyncSessionLocal() as s:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        s.add(PetSpecies(
            id="t21c-vis", name="Vis", rarity="common", color="#fff",
            frames=[], behavior={}, stats={},
            visible=True, sort_order=900,
            created_at=now, updated_at=now,
        ))
        s.add(PetSpecies(
            id="t21c-hid", name="Hid", rarity="common", color="#000",
            frames=[], behavior={}, stats={},
            visible=False, sort_order=901,
            created_at=now, updated_at=now,
        ))
        await s.commit()

    r = await client.get("/api/pet/species")
    assert r.status_code == 200, r.text
    ids = [row["id"] for row in r.json()]
    assert "t21c-vis" in ids
    assert "t21c-hid" not in ids


async def test_public_list_orders_by_sort_then_id(client):
    r = await client.get("/api/pet/species")
    assert r.status_code == 200
    rows = r.json()
    sort_orders = [row["sort_order"] for row in rows]
    assert sort_orders == sorted(sort_orders), "rows should be ordered by sort_order asc"


# ------------------------------- admin list --------------------------------

async def test_admin_list_requires_session(client):
    r = await client.get("/api/admin/pet/species")
    assert r.status_code == 401


async def test_admin_list_includes_hidden(client, admin_token, cleanup_t21c):
    async with AsyncSessionLocal() as s:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        s.add(PetSpecies(
            id="t21c-hid2", name="Hid2", rarity="common", color="#000",
            frames=[], behavior={}, stats={},
            visible=False, sort_order=902,
            created_at=now, updated_at=now,
        ))
        await s.commit()

    r = await client.get("/api/admin/pet/species", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    ids = [row["id"] for row in r.json()]
    assert "t21c-hid2" in ids


# --------------------------------- create ----------------------------------

async def test_create_round_trips(client, admin_token, cleanup_t21c):
    body = {
        "id": "t21c-newkin",
        "name": "Newkin",
        "rarity": "rare",
        "color": "#a78bfa",
        "trait_zh": "测试搭子",
        "personality_zh": "可爱",
        "description_zh": "圆滚滚",
        "frames": [["frame1"], ["frame2"], ["frame3"]],
        "behavior": {"proactiveLevel": 3, "idleFrequency": "normal", "localLines": []},
        "stats": {"snark": 50},
        "visible": True,
        "sort_order": 999,
    }
    r = await client.post("/api/admin/pet/species", json=body, headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["id"] == "t21c-newkin"
    assert out["rarity"] == "rare"
    assert out["frames"] == [["frame1"], ["frame2"], ["frame3"]]
    # And it's listable
    r2 = await client.get("/api/admin/pet/species", headers=_auth(admin_token))
    assert "t21c-newkin" in [row["id"] for row in r2.json()]


async def test_create_rejects_duplicate(client, admin_token, cleanup_t21c):
    body = {"id": "t21c-dup", "name": "Dup", "rarity": "common", "color": "#fff", "frames": []}
    r1 = await client.post("/api/admin/pet/species", json=body, headers=_auth(admin_token))
    assert r1.status_code == 200
    r2 = await client.post("/api/admin/pet/species", json=body, headers=_auth(admin_token))
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


async def test_create_rejects_bad_slug(client, admin_token):
    body = {"id": "9bad", "name": "Bad", "rarity": "common", "color": "#fff", "frames": []}
    r = await client.post("/api/admin/pet/species", json=body, headers=_auth(admin_token))
    assert r.status_code == 422


async def test_create_rejects_unknown_rarity(client, admin_token, cleanup_t21c):
    body = {
        "id": "t21c-bad-rarity", "name": "X", "rarity": "mythic",
        "color": "#fff", "frames": [],
    }
    r = await client.post("/api/admin/pet/species", json=body, headers=_auth(admin_token))
    assert r.status_code == 422


# ---------------------------------- patch ----------------------------------

async def test_patch_updates_subset(client, admin_token, cleanup_t21c):
    create = await client.post(
        "/api/admin/pet/species",
        json={"id": "t21c-patch", "name": "Old", "rarity": "common",
              "color": "#fff", "frames": []},
        headers=_auth(admin_token),
    )
    assert create.status_code == 200

    r = await client.patch(
        "/api/admin/pet/species/t21c-patch",
        json={"name": "Renamed", "visible": False},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["name"] == "Renamed"
    assert out["visible"] is False
    # rarity unchanged
    assert out["rarity"] == "common"


async def test_patch_unknown_id_404(client, admin_token):
    r = await client.patch(
        "/api/admin/pet/species/t21c-missing",
        json={"name": "x"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 404


# --------------------------------- delete ----------------------------------

async def test_delete_round_trips(client, admin_token, cleanup_t21c):
    create = await client.post(
        "/api/admin/pet/species",
        json={"id": "t21c-del", "name": "Del", "rarity": "common",
              "color": "#fff", "frames": []},
        headers=_auth(admin_token),
    )
    assert create.status_code == 200

    r = await client.delete("/api/admin/pet/species/t21c-del", headers=_auth(admin_token))
    assert r.status_code == 204

    r2 = await client.get("/api/admin/pet/species", headers=_auth(admin_token))
    assert "t21c-del" not in [row["id"] for row in r2.json()]


async def test_delete_refuses_default_pet_species(client, admin_token, cleanup_t21c):
    create = await client.post(
        "/api/admin/pet/species",
        json={"id": "t21c-defaultpet", "name": "Default", "rarity": "common",
              "color": "#fff", "frames": []},
        headers=_auth(admin_token),
    )
    assert create.status_code == 200

    # Park t21c-defaultpet as the site default pet, then attempt delete.
    async with AsyncSessionLocal() as s:
        site = (await s.execute(__import__("sqlalchemy").select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
        old_cfg = dict(site.pet_config or {})
        new_cfg = {**old_cfg, "species": "t21c-defaultpet"}
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=new_cfg))
        await s.commit()
    try:
        r = await client.delete(
            "/api/admin/pet/species/t21c-defaultpet", headers=_auth(admin_token)
        )
        assert r.status_code == 409
        assert "default pet" in r.json()["detail"].lower()
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=old_cfg))
            await s.commit()


async def test_delete_unknown_id_404(client, admin_token):
    r = await client.delete("/api/admin/pet/species/t21c-missing", headers=_auth(admin_token))
    assert r.status_code == 404


# --------------------- write actions reject api-token? ---------------------

async def test_write_endpoints_accept_write_scope_token(client, admin_token, cleanup_t21c):
    """API tokens with write scope should be able to create/edit species."""
    # Create token
    cr = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t21c", "scope": "write"},
        headers=_auth(admin_token),
    )
    assert cr.status_code == 200
    raw = cr.json()["token"]
    try:
        r = await client.post(
            "/api/admin/pet/species",
            json={"id": "t21c-tok", "name": "Tok", "rarity": "common",
                  "color": "#fff", "frames": []},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200, r.text
    finally:
        from app.models import ApiToken
        async with AsyncSessionLocal() as s:
            await s.execute(delete(ApiToken))
            await s.commit()


async def test_write_endpoints_reject_read_scope_token(client, admin_token):
    cr = await client.post(
        "/api/admin/api-tokens",
        json={"name": "t21c-r", "scope": "read"},
        headers=_auth(admin_token),
    )
    assert cr.status_code == 200
    raw = cr.json()["token"]
    try:
        r = await client.post(
            "/api/admin/pet/species",
            json={"id": "t21c-ro", "name": "Ro", "rarity": "common",
                  "color": "#fff", "frames": []},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code in (401, 403), r.text
    finally:
        from app.models import ApiToken
        async with AsyncSessionLocal() as s:
            await s.execute(delete(ApiToken))
            await s.commit()
