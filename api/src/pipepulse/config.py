import re
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PIPEPULSE_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pipepulse:pipepulse@localhost:5432/pipepulse"
    # Internal: marks an instance serving generated demo data (seed). Not for regular use.
    demo_mode: bool = False

    # The GitLab instance and projects to track. The worker adds listed projects and marks the
    # ones no longer listed as removed; their history goes once deleted from the dashboard.
    gitlab_url: str = "https://gitlab.com"
    # Personal/project/group access token with the read_api scope.
    gitlab_token: SecretStr | None = None
    # "group/project" paths, separated by commas, spaces or newlines. Empty = every project the
    # token can see pipelines of (Reporter access and up, not archived, CI enabled).
    projects: str = ""

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

    @property
    def project_paths(self) -> list[str]:
        """Configured project paths, deduplicated case-insensitively, in the given order."""
        seen: dict[str, str] = {}
        for path in re.split(r"[\s,]+", self.projects):
            path = path.strip().strip("/")
            if path and path.lower() not in seen:
                seen[path.lower()] = path
        return list(seen.values())


@lru_cache
def get_settings() -> Settings:
    return Settings()
