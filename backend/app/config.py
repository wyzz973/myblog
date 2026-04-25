from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # core
    api_port: int = 51820
    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # storage
    database_url: str
    redis_url: str
    data_dir: Path = Path("./data")
    posts_dir: Path = Path("./posts")

    # auth
    jwt_secret: str = Field(min_length=32)
    access_token_ttl: int = 900

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
