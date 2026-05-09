from pathlib import Path

import pytest

from myblog import config


def test_credentials_path_uses_xdg(tmp_home: Path) -> None:
    p = config.credentials_path()
    assert p == tmp_home / ".config" / "myblog" / "credentials.toml"


def test_load_credentials_missing(tmp_home: Path) -> None:
    with pytest.raises(config.NotConfigured) as ei:
        config.load_credentials()
    assert "myblog auth login" in str(ei.value)


def test_save_then_load_credentials(tmp_home: Path) -> None:
    config.save_credentials(base_url="https://example.test", admin_token="t0k")
    loaded = config.load_credentials()
    assert loaded.base_url == "https://example.test"
    assert loaded.admin_token == "t0k"


def test_save_credentials_chmod_600(tmp_home: Path) -> None:
    config.save_credentials(base_url="https://x", admin_token="y")
    mode = (tmp_home / ".config" / "myblog" / "credentials.toml").stat().st_mode & 0o777
    assert mode == 0o600


def test_find_repo_root_walks_up(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_repo / "deep" / "nested"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert config.find_repo_root() == tmp_repo


def test_load_deploy_env(tmp_repo: Path) -> None:
    env = config.load_deploy_env()
    assert env.server == "root@example.com"
    assert env.sshpass == "secret"
    assert env.domain == "example.com"


def test_load_deploy_env_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(config.NotConfigured) as ei:
        config.load_deploy_env()
    assert ".env.deploy" in str(ei.value)
