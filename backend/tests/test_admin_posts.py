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
