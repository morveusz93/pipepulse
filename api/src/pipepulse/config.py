from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PIPEPULSE_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pipepulse:pipepulse@localhost:5432/pipepulse"
    # Fernet key used to encrypt GitLab tokens at rest. Never commit a real one.
    encryption_key: SecretStr | None = None
    # Public demo instance: serve seed data only, never accept user tokens.
    demo_mode: bool = True
    poll_interval_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
