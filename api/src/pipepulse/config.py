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
    # Self-hosted mode: single admin who manages GitLab connections. Unset = nobody can log in.
    admin_password: SecretStr | None = None
    session_ttl_hours: int = 12
    # Browsers treat localhost as secure, so this can stay on for local development too.
    cookie_secure: bool = True
    poll_interval_seconds: int = 120
    # How far back the first sync of a new project reaches.
    backfill_days: int = 30
    trace_tail_lines: int = 50
    # Pipeline sources that aren't regular CI runs and would skew trends.
    # Env override is a JSON list, e.g. PIPEPULSE_IGNORED_SOURCES='["duo_workflow"]'.
    ignored_sources: set[str] = {
        "duo_workflow",
        "parent_pipeline",
        "ondemand_dast_scan",
        "ondemand_dast_validation",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
