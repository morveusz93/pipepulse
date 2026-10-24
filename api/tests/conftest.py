import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipepulse.models import Base

TEST_DATABASE_URL = os.environ.get(
    "PIPEPULSE_TEST_DATABASE_URL",
    "postgresql+psycopg://pipepulse:pipepulse@localhost:5432/pipepulse_test",
)


@pytest.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh schema per test on a real Postgres (`docker compose up postgres`)."""
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except OperationalError:
        await engine.dispose()
        pytest.skip(f"test database unavailable at {TEST_DATABASE_URL}")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
