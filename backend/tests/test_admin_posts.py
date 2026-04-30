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
