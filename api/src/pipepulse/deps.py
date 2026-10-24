from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.config import Settings, get_settings
from pipepulse.crypto import TokenCipher
from pipepulse.db import get_session
from pipepulse.gitlab import GitLabClient
from pipepulse.schemas import Scope


def get_now() -> datetime:
    """Overridable in tests, so time windows are deterministic."""
    return datetime.now(UTC)


SessionDep = Annotated[AsyncSession, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
DaysQuery = Annotated[int, Query(ge=1, le=90, description="Window length in days")]
ScopeQuery = Annotated[
    Scope, Query(description="default = project's default branch only, all = every ref")
]


def get_token_cipher(settings: Annotated[Settings, Depends(get_settings)]) -> TokenCipher:
    key = settings.encryption_key.get_secret_value() if settings.encryption_key else ""
    return TokenCipher(key)


GitLabClientFactory = Callable[[str, str], GitLabClient]


def get_gitlab_client_factory() -> GitLabClientFactory:
    return GitLabClient


CipherDep = Annotated[TokenCipher, Depends(get_token_cipher)]
GitLabFactoryDep = Annotated[GitLabClientFactory, Depends(get_gitlab_client_factory)]
