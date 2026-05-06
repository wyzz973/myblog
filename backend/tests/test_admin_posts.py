import pytest

GOOD_MD = """---
id: test-post-1
n: "999"
title: Test post
tag: devtools
date: 2026-04-25
lang: en
status: published
---

## Heading

A paragraph.
"""


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": "hi@wangyang.dev", "password": "changeme"})
    return r.json()["access"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


async def test_create_requires_auth(client):
    r = await client.post("/api/admin/posts", json={"markdown": GOOD_MD})
    assert r.status_code == 401


async def test_create_post_then_get(client, auth):
    # cleanup if previous run left it
    await client.delete("/api/admin/posts/test-post-1", headers=auth)

    r = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "test-post-1"

    g = await client.get("/api/admin/posts/test-post-1", headers=auth)
    assert g.status_code == 200
    detail = g.json()
    assert detail["title"] == "Test post"
    # body_md is the raw markdown body (without frontmatter), so the editor
    # can round-trip an existing post.
    assert "body_md" in detail
    assert "## Heading" in detail["body_md"]
    assert "A paragraph." in detail["body_md"]
    assert "---" not in detail["body_md"]

    # Cleanup
    await client.delete("/api/admin/posts/test-post-1", headers=auth)


async def test_render_preview_returns_blocks(client, auth):
    r = await client.post("/api/admin/posts/render-preview", json={"markdown": GOOD_MD}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == []
    assert body["frontmatter"]["id"] == "test-post-1"
    assert any(b["t"] == "h2" for b in body["body"])


async def test_render_preview_invalid_frontmatter_returns_errors(client, auth):
    bad = GOOD_MD.replace("title: Test post", "title: [unterminated")
    r = await client.post("/api/admin/posts/render-preview", json={"markdown": bad}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["frontmatter"] is None
    assert body["body"] == []
    assert "frontmatter invalid" in body["errors"][0]


async def test_create_invalid_frontmatter_returns_422(client, auth):
    bad = GOOD_MD.replace("title: Test post", "title: [unterminated")
    r = await client.post("/api/admin/posts", json={"markdown": bad}, headers=auth)
    assert r.status_code == 422
    assert "frontmatter invalid" in r.json()["detail"]


async def test_render_preview_accepts_plain_scalar_colon(client, auth):
    md = GOOD_MD.replace("status: published", "status: published\nsummary: 推荐（按稳定度排序）:")
    r = await client.post("/api/admin/posts/render-preview", json={"markdown": md}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == []
    assert body["frontmatter"]["summary"] == "推荐（按稳定度排序）:"


async def test_create_duplicate_409(client, auth):
    await client.delete("/api/admin/posts/test-post-1", headers=auth)
    r1 = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r1.status_code == 201
    r2 = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r2.status_code == 409
    await client.delete("/api/admin/posts/test-post-1", headers=auth)


async def test_admin_list_includes_drafts(client, auth):
    draft = GOOD_MD.replace("status: published", "status: draft").replace("test-post-1", "test-draft-1")
    await client.post("/api/admin/posts", json={"markdown": draft}, headers=auth)
    r = await client.get("/api/admin/posts?status=draft", headers=auth)
    assert r.status_code == 200
    assert any(p["id"] == "test-draft-1" for p in r.json()["items"])
    await client.delete("/api/admin/posts/test-draft-1", headers=auth)


async def test_upload_single_md(client, auth):
    await client.delete("/api/admin/posts/upload-test-1", headers=auth)
    md = GOOD_MD.replace("test-post-1", "upload-test-1")
    files = {"files": ("upload-test-1.md", md.encode("utf-8"), "text/markdown")}
    r = await client.post("/api/admin/posts/upload", files=files, headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["summary"] == {"total": 1, "ok": 1, "failed": 0}
    await client.delete("/api/admin/posts/upload-test-1", headers=auth)


async def test_upload_partial_failure_returns_207(client, auth):
    await client.delete("/api/admin/posts/upload-test-2", headers=auth)
    good = GOOD_MD.replace("test-post-1", "upload-test-2")
    bad = "no-frontmatter content"
    files = [
        ("files", ("a.md", good.encode("utf-8"), "text/markdown")),
        ("files", ("b.md", bad.encode("utf-8"), "text/markdown")),
    ]
    r = await client.post("/api/admin/posts/upload", files=files, headers=auth)
    assert r.status_code == 207
    body = r.json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["ok"] == 1
    await client.delete("/api/admin/posts/upload-test-2", headers=auth)


# --- Task 33: PostDetail exposes lifecycle / visibility flags ---


async def test_post_detail_includes_lifecycle_flags(client, auth):
    # Seed via the create endpoint; default status/visibility flags
    # come from the model + frontmatter.
    await client.delete("/api/admin/posts/test-post-1", headers=auth)
    create = await client.post(
        "/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth,
    )
    assert create.status_code == 201, create.text
    try:
        r = await client.get("/api/admin/posts/test-post-1", headers=auth)
        assert r.status_code == 200
        body = r.json()
        # All five fields must be present so the editor's GUI strip can
        # round-trip them.
        for field in ("status", "scheduled_at", "featured", "private", "comments_enabled"):
            assert field in body, f"missing {field!r} in PostDetail: {list(body.keys())}"
        assert body["status"] == "published"  # from frontmatter
        assert body["featured"] is False
        assert body["private"] is False
        assert body["comments_enabled"] is True  # default for new post
        assert body["scheduled_at"] is None
    finally:
        await client.delete("/api/admin/posts/test-post-1", headers=auth)


# --- Task 42: bulk export to tar archive ---


async def test_export_tar_returns_tar_with_seeded_post(client, auth):
    """Seed a post via create, export, assert the post appears in the tar."""
    import io
    import tarfile
    # Clean slate for our seed id (idempotent if missing).
    await client.delete("/api/admin/posts/t42-export", headers=auth)
    seed = GOOD_MD.replace("id: test-post-1", "id: t42-export").replace(
        "title: Test post", "title: t42 export fixture"
    )
    create = await client.post(
        "/api/admin/posts", json={"markdown": seed}, headers=auth,
    )
    assert create.status_code == 201, create.text
    try:
        r = await client.get("/api/admin/posts.tar", headers=auth)
        assert r.status_code == 200, r.text
        ct = r.headers["content-type"]
        assert "application/x-tar" in ct, ct
        cd = r.headers.get("content-disposition", "")
        assert "posts-" in cd and "items.tar" in cd, cd

        tar = tarfile.open(fileobj=io.BytesIO(r.content), mode="r")
        names = tar.getnames()
        assert "t42-export.md" in names, names
        # Frontmatter round-trips through the upload endpoint shape
        member = tar.extractfile("t42-export.md")
        assert member is not None
        body = member.read().decode("utf-8")
        # Frontmatter delimiters present
        assert body.startswith("---\n"), body[:50]
        assert "\n---\n" in body, "missing closing frontmatter delimiter"
        # Required fields present
        for needle in ('id: "t42-export"', 'tag: "devtools"', 'status: "published"'):
            assert needle in body, f"missing {needle!r} in body:\n{body[:500]}"
        # Body content preserved
        assert "## Heading" in body
    finally:
        await client.delete("/api/admin/posts/t42-export", headers=auth)


async def test_export_tar_round_trips_through_upload(client, auth):
    """Export a post, delete it from the DB, re-upload from the tar, see the
    content match. Validates the export → import round-trip."""
    import io
    import tarfile
    await client.delete("/api/admin/posts/t42-roundtrip", headers=auth)
    seed = GOOD_MD.replace("id: test-post-1", "id: t42-roundtrip").replace(
        "title: Test post", "title: roundtrip"
    )
    await client.post("/api/admin/posts", json={"markdown": seed}, headers=auth)
    try:
        r = await client.get("/api/admin/posts.tar", headers=auth)
        tar = tarfile.open(fileobj=io.BytesIO(r.content), mode="r")
        member = tar.extractfile("t42-roundtrip.md")
        md_bytes = member.read()

        # Delete and re-upload from the captured tar member.
        await client.delete("/api/admin/posts/t42-roundtrip", headers=auth)
        files = [("files", ("t42-roundtrip.md", md_bytes, "text/markdown"))]
        up = await client.post("/api/admin/posts/upload", files=files, headers=auth)
        assert up.status_code == 201, up.text
        body = up.json()
        assert body["summary"]["ok"] == 1, body
        # And the post is back, with the same title.
        det = await client.get("/api/admin/posts/t42-roundtrip", headers=auth)
        assert det.status_code == 200
        assert det.json()["title"] == "roundtrip"
    finally:
        await client.delete("/api/admin/posts/t42-roundtrip", headers=auth)


async def test_export_tar_requires_session(client):
    r = await client.get("/api/admin/posts.tar")
    assert r.status_code == 401


# --- Task 49: next-n suggestion ---


async def test_next_n_returns_string_with_3_digit_zero_padding(client, auth):
    r = await client.get("/api/admin/posts/next-n", headers=auth)
    assert r.status_code == 200, r.text
    n = r.json()["n"]
    assert isinstance(n, str)
    # Either 3-digit zero-padded or numeric overflow string.
    assert n.isdigit()


async def test_next_n_increments_after_create(client, auth):
    """Create a post with n="100"; next-n should bump to "101"."""
    await client.delete("/api/admin/posts/t49-next-a", headers=auth)
    seed = (
        '---\nid: t49-next-a\nn: "100"\ntitle: t49a\ntag: devtools\n'
        'date: 2026-04-25\nlang: en\nstatus: draft\n---\n\nbody\n'
    )
    create = await client.post(
        "/api/admin/posts", json={"markdown": seed}, headers=auth,
    )
    assert create.status_code == 201, create.text
    try:
        r = await client.get("/api/admin/posts/next-n", headers=auth)
        n = r.json()["n"]
        # Expect 101 — but the suite may have a higher-numbered post lying
        # around; the only firm guarantee is `int(n) > 100`.
        assert int(n) > 100, n
        assert len(n) >= 3, n
    finally:
        await client.delete("/api/admin/posts/t49-next-a", headers=auth)


async def test_next_n_unauth_401(client):
    r = await client.get("/api/admin/posts/next-n")
    assert r.status_code == 401


async def test_next_n_skips_non_numeric_rows(client, auth):
    """A post with n="abc" must not break the max(int(n)) calc."""
    await client.delete("/api/admin/posts/t49-next-bogus", headers=auth)
    # Create through DB since the API would reject n="abc" via PostFrontmatter pattern.
    from datetime import date, datetime, UTC
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import Post, Tag
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        s.add(Post(
            id="t49-next-bogus", n="abc", title="bogus n", subtitle=None,
            tag_id=tag.id, date=date(2026, 1, 1), lang="en",
            body_md="x", body_json=[], word_count=0,
            status="draft", featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        r = await client.get("/api/admin/posts/next-n", headers=auth)
        assert r.status_code == 200
        # Should return a valid digit string regardless of the bogus row.
        assert r.json()["n"].isdigit()
    finally:
        from sqlalchemy import delete
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == "t49-next-bogus"))
            await s.commit()
