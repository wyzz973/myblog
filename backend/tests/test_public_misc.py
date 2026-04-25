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
