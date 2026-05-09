import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_media_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/media").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "filename": "a.png", "url": "/m/a.png"}])
    )
    res = CliRunner().invoke(app, ["media", "list"])
    assert res.exit_code == 0
    assert "a.png" in res.stdout


@respx.mock
def test_media_upload(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    f = tmp_path / "x.png"
    f.write_bytes(b"\x89PNG")
    route = respx.post("https://example.test/api/admin/media").mock(
        return_value=httpx.Response(201, json={"id": 7, "url": "/m/x.png"})
    )
    res = CliRunner().invoke(app, ["media", "upload", str(f), "--alt", "hello"])
    assert res.exit_code == 0
    body = route.calls.last.request.read()
    assert b'name="file"' in body
    assert b'name="alt"' in body and b"hello" in body


@respx.mock
def test_media_rm_dry_run(tmp_home) -> None:
    _seed(tmp_home)
    res = CliRunner().invoke(app, ["media", "rm", "7"])
    assert res.exit_code == 1


@respx.mock
def test_media_rm_yes(tmp_home) -> None:
    _seed(tmp_home)
    respx.delete("https://example.test/api/admin/media/7").mock(
        return_value=httpx.Response(204)
    )
    res = CliRunner().invoke(app, ["media", "rm", "7", "--yes"])
    assert res.exit_code == 0
