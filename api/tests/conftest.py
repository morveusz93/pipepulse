import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipepulse.auth import login_limiter
from pipepulse.config import Settings, get_settings
from pipepulse.db import get_session
from pipepulse.deps import get_gitlab_client_factory, get_now
from pipepulse.main import app
from pipepulse.models import Base
from tests.fake_gitlab import FakeGitLab

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
ADMIN_PASSWORD = "correct horse battery staple"

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


@pytest.fixture
def settings() -> Settings:
    """Self-hosted instance with admin login enabled. Tests tweak fields as needed."""
    return Settings(
        demo_mode=False,
        admin_password=SecretStr(ADMIN_PASSWORD),
        encryption_key=SecretStr(Fernet.generate_key().decode()),
        cookie_secure=False,  # the test client talks plain http to a non-localhost host
    )


@pytest.fixture
def fake_gitlab() -> FakeGitLab:
    return FakeGitLab()


@pytest.fixture
async def client(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    fake_gitlab: FakeGitLab,
) -> AsyncIterator[httpx.AsyncClient]:
    async def session_override() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_gitlab_client_factory] = lambda: fake_gitlab.client
    login_limiter.reset()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
