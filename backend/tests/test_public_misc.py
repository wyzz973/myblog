async def test_site_payload_shape(client):
    r = await client.get("/api/site")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "handle", "name", "name_en", "role", "tagline", "bio", "location", "email", "github",
        "uptime", "posts", "words", "commits52w", "footer_note",
        "default_theme", "accent_color", "accent2_color", "violet_color", "danger_color",
    ):
        assert key in body, f"missing key: {key}"
    assert isinstance(body["uptime"], str)
    assert body["posts"] >= 0


async def test_contacts_returns_list(client):
    r = await client.get("/api/contacts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_tags_includes_all(client):
    r = await client.get("/api/tags")
    assert r.status_code == 200
    body = r.json()
    assert any(t["id"] == "all" for t in body)
    assert all(set(t.keys()) == {"id", "label", "n"} for t in body)


async def test_projects_returns_list(client):
    r = await client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        assert set(body[0].keys()) == {"name", "desc", "lang", "stars", "status"}


async def test_contrib_returns_grid(client):
    r = await client.get("/api/contrib")
    assert r.status_code == 200
    body = r.json()
    assert body["weeks"] == 52
    assert len(body["grid"]) == 52
    assert all(len(col) == 7 for col in body["grid"])
    # Phase-9d removed the LCG seed-fallback; empty DB now reports "empty".
    assert body["source"] in ("github", "empty")
