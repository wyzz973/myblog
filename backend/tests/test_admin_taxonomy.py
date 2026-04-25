import pytest


@pytest.fixture
async def auth(client):
    r = await client.post(
        "/api/admin/auth/login",
        json={"email": "hi@wangyang.dev", "password": "changeme"},
    )
    return {"Authorization": f"Bearer {r.json()['access']}"}


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


async def test_tags_list_returns_seeded(client, auth):
    r = await client.get("/api/admin/tags", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert any(t["slug"] == "backend" for t in body)


async def test_tags_create_patch_delete(client, auth):
    # cleanup leftovers
    listing = await client.get("/api/admin/tags", headers=auth)
    for t in listing.json():
        if t["slug"] == "tmp-tag":
            await client.delete(f"/api/admin/tags/{t['id']}", headers=auth)

    create = await client.post(
        "/api/admin/tags",
        json={"slug": "tmp-tag", "name": "tmp", "color": "#ff00ff", "sort_order": 99},
        headers=auth,
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]

    patch = await client.patch(
        f"/api/admin/tags/{tid}", json={"name": "renamed"}, headers=auth
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "renamed"

    deleted = await client.delete(f"/api/admin/tags/{tid}", headers=auth)
    assert deleted.status_code == 204


async def test_tags_reorder(client, auth):
    listing = await client.get("/api/admin/tags", headers=auth)
    ids = [t["id"] for t in listing.json()]
    reordered = list(reversed(ids))
    r = await client.put(
        "/api/admin/tags/order", json={"ids": reordered}, headers=auth
    )
    assert r.status_code == 204


async def test_tags_reorder_rejects_bad_payload(client, auth):
    r = await client.put(
        "/api/admin/tags/order", json={"ids": "nope"}, headers=auth
    )
    assert r.status_code == 422
