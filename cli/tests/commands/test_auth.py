import json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def test_login_writes_credentials(tmp_home) -> None:
    runner = CliRunner()
    res = runner.invoke(
        app, ["auth", "login"],
        input="https://example.test\nsecret-token\n",
    )
    assert res.exit_code == 0, res.stdout
    creds = config.load_credentials()
    assert creds.base_url == "https://example.test"
    assert creds.admin_token == "secret-token"


def test_token_set_replaces_token(tmp_home) -> None:
    config.save_credentials(base_url="https://x", admin_token="old")
    runner = CliRunner()
    res = runner.invoke(app, ["auth", "token-set", "new"])
    assert res.exit_code == 0
    assert config.load_credentials().admin_token == "new"


@respx.mock
def test_whoami_200(tmp_home) -> None:
    config.save_credentials(base_url="https://example.test", admin_token="ok")
    respx.get("https://example.test/api/admin/site").mock(
        return_value=httpx.Response(200, json={"handle": "wyz"})
    )
    runner = CliRunner()
    res = runner.invoke(app, ["--json", "auth", "whoami"])
    assert res.exit_code == 0
    line = json.loads(res.stdout.splitlines()[0])
    assert line["base_url"] == "https://example.test"
    assert line["ok"] is True


@respx.mock
def test_whoami_401(tmp_home) -> None:
    config.save_credentials(base_url="https://example.test", admin_token="bad")
    respx.get("https://example.test/api/admin/site").mock(
        return_value=httpx.Response(401, json={"detail": "bad token"})
    )
    runner = CliRunner()
    res = runner.invoke(app, ["auth", "whoami"])
    assert res.exit_code == 1
    assert "bad token" in res.stdout or "bad token" in res.stderr


def test_whoami_no_credentials_friendly_error(tmp_home, capsys) -> None:
    """When credentials are missing, surface a friendly error not a traceback."""
    from myblog.__main__ import main_entrypoint
    import sys
    sys.argv = ["myblog", "auth", "whoami"]
    try:
        main_entrypoint()
    except SystemExit as e:
        assert e.code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "auth login" in captured.err or "auth login" in captured.out
