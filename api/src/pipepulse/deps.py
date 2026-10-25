from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.config import Settings, get_settings
from pipepulse.db import get_session
from pipepulse.schemas import Scope


def get_now() -> datetime:
    """Overridable in tests, so time windows are deterministic."""
    return datetime.now(UTC)


SessionDep = Annotated[AsyncSession, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DaysQuery = Annotated[int, Query(ge=1, le=90, description="Window length in days")]
ScopeQuery = Annotated[
    Scope, Query(description="default = project's default branch only, all = every ref")
]
