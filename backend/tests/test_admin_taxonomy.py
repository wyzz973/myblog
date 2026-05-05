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


async def test_tags_list_returns_array(client, auth):
    r = await client.get("/api/admin/tags", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


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


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


async def test_projects_list_returns_array(client, auth):
    r = await client.get("/api/admin/projects", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_projects_create_patch_delete(client, auth):
    name = "tmp-project-x"
    await client.delete(f"/api/admin/projects/{name}", headers=auth)
    create = await client.post(
        "/api/admin/projects",
        json={
            "name": name,
            "description": "tmp",
            "lang": "Go",
            "stars": 0,
            "status": "active",
        },
        headers=auth,
    )
    assert create.status_code == 201, create.text
    patch = await client.patch(
        f"/api/admin/projects/{name}", json={"stars": 99}, headers=auth
    )
    assert patch.status_code == 200
    assert patch.json()["stars"] == 99
    deleted = await client.delete(f"/api/admin/projects/{name}", headers=auth)
    assert deleted.status_code == 204


async def test_projects_reorder(client, auth):
    listing = await client.get("/api/admin/projects", headers=auth)
    names = [p["name"] for p in listing.json()]
    reordered = list(reversed(names))
    r = await client.put(
        "/api/admin/projects/order", json={"ids": reordered}, headers=auth
    )
    assert r.status_code == 204


async def test_projects_reorder_rejects_int_ids(client, auth):
    r = await client.put(
        "/api/admin/projects/order", json={"ids": [1, 2, 3]}, headers=auth
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


async def test_contacts_list(client, auth):
    r = await client.get("/api/admin/contacts", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_contacts_create_patch_delete(client, auth):
    create = await client.post(
        "/api/admin/contacts",
        json={
            "label": "test",
            "value": "v",
            "href": "https://e",
            "visible": True,
            "sort_order": 0,
        },
        headers=auth,
    )
    assert create.status_code == 201, create.text
    cid = create.json()["id"]
    patch = await client.patch(
        f"/api/admin/contacts/{cid}", json={"value": "v2"}, headers=auth
    )
    assert patch.status_code == 200
    assert patch.json()["value"] == "v2"
    deleted = await client.delete(f"/api/admin/contacts/{cid}", headers=auth)
    assert deleted.status_code == 204


async def test_contacts_reorder(client, auth):
    # create two transient contacts to reorder
    a = await client.post(
        "/api/admin/contacts",
        json={
            "label": "a",
            "value": "a",
            "href": "https://a",
            "visible": True,
            "sort_order": 0,
        },
        headers=auth,
    )
    b = await client.post(
        "/api/admin/contacts",
        json={
            "label": "b",
            "value": "b",
            "href": "https://b",
            "visible": True,
            "sort_order": 1,
        },
        headers=auth,
    )
    assert a.status_code == 201
    assert b.status_code == 201
    aid, bid = a.json()["id"], b.json()["id"]
    try:
        r = await client.put(
            "/api/admin/contacts/order",
            json={"ids": [bid, aid]},
            headers=auth,
        )
        assert r.status_code == 204
    finally:
        await client.delete(f"/api/admin/contacts/{aid}", headers=auth)
        await client.delete(f"/api/admin/contacts/{bid}", headers=auth)


async def test_contacts_reorder_rejects_bad_payload(client, auth):
    r = await client.put(
        "/api/admin/contacts/order", json={"ids": "nope"}, headers=auth
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Task 30: tags reference scan + 409 delete refusal
# ---------------------------------------------------------------------------


async def test_tags_list_includes_post_count(client, auth):
    r = await client.get("/api/admin/tags", headers=auth)
    assert r.status_code == 200
    rows = r.json()
    # Every row should now expose post_count (>= 0) — the field was added so
    # the admin UI can warn / disable delete for tags still in use.
    assert all("post_count" in t for t in rows), rows
    assert all(isinstance(t["post_count"], int) for t in rows), rows
    assert all(t["post_count"] >= 0 for t in rows), rows


async def test_tags_delete_409_when_posts_reference_it(client, auth):
    # Seed: create a tag, attach a post to it, then try to delete the tag.
    from datetime import date as _d
    from sqlalchemy import delete as sa_delete
    from app.db import AsyncSessionLocal
    from app.models import Post, Tag
    create = await client.post(
        "/api/admin/tags",
        json={"slug": "t30-in-use", "name": "in-use", "color": "#aaa", "sort_order": 99},
        headers=auth,
    )
    assert create.status_code == 201
    tid = create.json()["id"]
    slug = "t30-post-ref"
    async with AsyncSessionLocal() as s:
        s.add(Post(
            id=slug, n="1", title="t30", subtitle="", date=_d(2026, 4, 28),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=tid,
        ))
        await s.commit()
    try:
        r = await client.delete(f"/api/admin/tags/{tid}", headers=auth)
        assert r.status_code == 409, r.text
        assert "post" in r.json()["detail"].lower()
        # Tag should still exist after refusal.
        listing2 = (await client.get("/api/admin/tags", headers=auth)).json()
        assert any(t["id"] == tid for t in listing2)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(Post).where(Post.id == slug))
            await s.commit()
        # Now delete should succeed
        r2 = await client.delete(f"/api/admin/tags/{tid}", headers=auth)
        assert r2.status_code == 204


async def test_tags_delete_204_when_no_posts(client, auth):
    create = await client.post(
        "/api/admin/tags",
        json={"slug": "t30-empty", "name": "empty", "color": "#aaa", "sort_order": 99},
        headers=auth,
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]
    # Fresh tag has no posts → delete must succeed.
    r = await client.delete(f"/api/admin/tags/{tid}", headers=auth)
    assert r.status_code == 204
