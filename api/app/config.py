"""Settings, read once from the environment.

`encryption_key` is validated on the way in, so a missing or malformed key stops
the service at startup. The failure to avoid is starting anyway and writing
secrets in the clear.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security.encryption import decode_key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    encryption_key: str

    @field_validator("encryption_key")
    @classmethod
    def check_encryption_key(cls, value: str) -> str:
        decode_key(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
