import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_post_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/posts").mock(
        return_value=httpx.Response(200, json={
            "items": [{"id": "p1", "title": "T1", "status": "published", "tag": "g"}],
            "total": 1, "limit": 20, "offset": 0,
        })
    )
    res = CliRunner().invoke(app, ["post", "list"])
    assert res.exit_code == 0
    assert "p1" in res.stdout


@respx.mock
def test_post_publish_uses_patch_status(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.patch("https://example.test/api/admin/posts/p1").mock(
        return_value=httpx.Response(200, json={"id": "p1", "status": "published"})
    )
    res = CliRunner().invoke(app, ["post", "publish", "p1"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"status": "published"}


@respx.mock
def test_post_delete_dry_run(tmp_home) -> None:
    _seed(tmp_home)
    res = CliRunner().invoke(app, ["post", "delete", "p1"])
    assert res.exit_code == 1
    assert "dry-run" in res.stdout.lower()


@respx.mock
def test_post_delete_yes(tmp_home) -> None:
    _seed(tmp_home)
    respx.delete("https://example.test/api/admin/posts/p1").mock(
        return_value=httpx.Response(204)
    )
    res = CliRunner().invoke(app, ["post", "delete", "p1", "--yes"])
    assert res.exit_code == 0


@respx.mock
def test_post_from_md_posts_markdown(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    md = tmp_path / "x.md"
    md.write_text("---\nid: hello\ntitle: Hi\ntag: notes\ndate: 2026-05-09\n---\nHello world.\n")
    route = respx.post("https://example.test/api/admin/posts").mock(
        return_value=httpx.Response(201, json={"id": "hello", "title": "Hi"})
    )
    res = CliRunner().invoke(app, ["post", "from-md", str(md)])
    assert res.exit_code == 0
    body = route.calls.last.request.read()
    assert b"Hello world." in body
    assert b"id: hello" in body


@respx.mock
def test_post_new_assembles_frontmatter(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/posts/next-n").mock(
        return_value=httpx.Response(200, json={"n": "042"})
    )
    route = respx.post("https://example.test/api/admin/posts").mock(
        return_value=httpx.Response(201, json={"id": "042-hello", "title": "Hello"})
    )
    res = CliRunner().invoke(app, ["post", "new", "--title", "Hello", "--tag", "notes", "--draft"])
    assert res.exit_code == 0
    body = route.calls.last.request.read().decode()
    assert "title: Hello" in body
    assert "tag: notes" in body
    assert "status: draft" in body
