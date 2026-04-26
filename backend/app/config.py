from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # core
    api_port: int = 51820
    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    # NoDecode disables pydantic-settings' default JSON-decode of list-typed env
    # vars, so the _split_csv validator below sees the raw "a,b,c" string.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    public_api_base_url: str = "http://localhost:51820"

    # storage
    database_url: str
    redis_url: str
    data_dir: Path = Path("./data")
    posts_dir: Path = Path("./posts")

    # auth
    jwt_secret: str = Field(min_length=32)
    access_token_ttl: int = 900
    refresh_token_ttl: int = 2_592_000      # 30 days
    magic_link_ttl: int = 900               # 15 minutes
    tfa_challenge_ttl: int = 300            # 5 minutes
    login_lockout_threshold: int = 10
    login_lockout_window_sec: int = 900     # 15 minutes
    secrets_key: SecretStr = Field(min_length=32)

    # salts
    like_salt: str = Field(min_length=16)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
