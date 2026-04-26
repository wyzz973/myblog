from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/d")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:51730")
    monkeypatch.setenv("SECRETS_KEY", "z" * 40)

    s = Settings()
    assert s.api_port == 51820
    assert s.env == "dev"
    assert str(s.database_url).startswith("postgresql+asyncpg://")
    assert s.cors_origins == ["http://localhost:51730"]


def test_cors_origins_csv(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/d")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://a,http://b")
    monkeypatch.setenv("SECRETS_KEY", "z" * 40)
    s = Settings()
    assert s.cors_origins == ["http://a", "http://b"]


def test_phase3_defaults(monkeypatch):
    """Defaults are correct when only required env vars are set."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 16)
    monkeypatch.setenv("SECRETS_KEY", "z" * 40)
    from app.config import Settings
    s = Settings(_env_file=None)  # bypass .env file entirely
    assert s.refresh_token_ttl == 2_592_000
    assert s.magic_link_ttl == 900
    assert s.tfa_challenge_ttl == 300
    assert s.login_lockout_threshold == 10
    assert s.login_lockout_window_sec == 900
    assert s.secrets_key.get_secret_value() == "z" * 40


def test_secrets_key_min_length_enforced(monkeypatch):
    """Field(min_length=32) on secrets_key rejects short values."""
    import pytest
    from pydantic import ValidationError
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 16)
    monkeypatch.setenv("SECRETS_KEY", "tooshort")
    from app.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_arq_inline_default_false(monkeypatch):
    """ARQ_INLINE defaults to False in production; tests override via env."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 16)
    monkeypatch.setenv("SECRETS_KEY", "z" * 40)
    monkeypatch.delenv("ARQ_INLINE", raising=False)
    from app.config import Settings
    s = Settings(_env_file=None)
    assert s.arq_inline is False


def test_arq_inline_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://x")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 16)
    monkeypatch.setenv("SECRETS_KEY", "z" * 40)
    monkeypatch.setenv("ARQ_INLINE", "true")
    from app.config import Settings
    s = Settings(_env_file=None)
    assert s.arq_inline is True
