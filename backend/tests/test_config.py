from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/d")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:51730")

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
    s = Settings()
    assert s.cors_origins == ["http://a", "http://b"]
