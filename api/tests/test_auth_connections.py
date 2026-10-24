from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.auth import SESSION_COOKIE, create_session, verify_session
from pipepulse.config import Settings
from pipepulse.crypto import TokenCipher
from pipepulse.models import Connection, Pipeline, Project
from tests.conftest import ADMIN_PASSWORD, NOW
from tests.fake_gitlab import PROJECT_ID, FakeGitLab

TOKEN = "glpat-" + "fake" * 5
NEW_CONNECTION = {"name": "work", "base_url": "https://gitlab.example.com/", "token": TOKEN}


async def login(client: httpx.AsyncClient, password: str = ADMIN_PASSWORD) -> httpx.Response:
    return await client.post("/api/auth/login", json={"password": password})


async def create_connection(client: httpx.AsyncClient) -> dict:
    response = await client.post("/api/connections", json=NEW_CONNECTION)
    assert response.status_code == 201, response.text
    return response.json()


# --- sessions ---------------------------------------------------------------------------------


def test_session_token_roundtrip_and_tampering(settings: Settings) -> None:
    token = create_session(settings, now=1_000)
    assert verify_session(settings, token, now=1_001)
    assert not verify_session(settings, token, now=1_000 + 13 * 3600)  # expired
    expires, signature = token.split(".")
    assert not verify_session(settings, f"{int(expires) + 3600}.{signature}", now=1_001)
    assert not verify_session(settings, "garbage", now=1_001)


async def test_login_sets_strict_httponly_cookie(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).json() == {
        "demo_mode": False,
        "admin_enabled": True,
        "authenticated": False,
    }

    response = await login(client)

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert ADMIN_PASSWORD not in cookie
    assert (await client.get("/api/auth/me")).json()["authenticated"] is True

    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).json()["authenticated"] is False


async def test_wrong_password_and_lockout(client: httpx.AsyncClient) -> None:
    for _ in range(5):
        assert (await login(client, "nope")).status_code == 401
    # Locked out even with the right password.
    assert (await login(client)).status_code == 429


async def test_admin_disabled_without_password(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    settings.admin_password = None
    assert (await client.get("/api/auth/me")).json()["admin_enabled"] is False
    assert (await login(client)).status_code == 503
    assert (await client.get("/api/connections")).status_code == 401


async def test_demo_mode_blocks_everything(client: httpx.AsyncClient, settings: Settings) -> None:
    await login(client)
    settings.demo_mode = True

    assert (await client.get("/api/auth/me")).json()["demo_mode"] is True
    assert (await login(client)).status_code == 403
    assert (await client.get("/api/connections")).status_code == 403
    assert (await client.post("/api/connections", json=NEW_CONNECTION)).status_code == 403


async def test_connections_require_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/connections")).status_code == 401
    assert (await client.post("/api/connections", json=NEW_CONNECTION)).status_code == 401
    assert (await client.delete("/api/projects/1")).status_code == 401
    client.cookies.set(SESSION_COOKIE, "9999999999.deadbeef")
    assert (await client.get("/api/connections")).status_code == 401


# --- connections ------------------------------------------------------------------------------


async def test_create_connection_stores_encrypted_token(
    client: httpx.AsyncClient,
    session: AsyncSession,
    settings: Settings,
    fake_gitlab: FakeGitLab,
) -> None:
    await login(client)
    created = await create_connection(client)

    assert created["base_url"] == "https://gitlab.example.com"
    assert created["token_masked"] == "****fake"
    assert created["warnings"] == []
    assert TOKEN not in str(created)
    assert fake_gitlab.tokens_seen == [TOKEN]

    stored = await session.scalar(select(Connection))
    assert TOKEN.encode() not in stored.token_encrypted
    cipher = TokenCipher(settings.encryption_key.get_secret_value())
    assert cipher.decrypt(stored.token_encrypted) == TOKEN

    [listed] = (await client.get("/api/connections")).json()
    assert listed["token_masked"] == "****fake" and listed["project_count"] == 0
    assert TOKEN not in str(listed)


@pytest.mark.parametrize(
    ("token_info", "status", "message"),
    [
        (401, 400, "rejected"),
        ({"name": "t", "scopes": ["read_user"], "active": True}, 400, "read_api"),
        ({"name": "t", "scopes": ["read_api"], "active": False}, 400, "not active"),
        (503, 502, "GitLab request failed"),
    ],
)
async def test_create_connection_rejects_bad_tokens(
    client: httpx.AsyncClient,
    session: AsyncSession,
    fake_gitlab: FakeGitLab,
    token_info: dict | int,
    status: int,
    message: str,
) -> None:
    fake_gitlab.token_info = token_info
    await login(client)

    response = await client.post("/api/connections", json=NEW_CONNECTION)

    assert response.status_code == status
    assert message in response.json()["detail"]
    assert await session.scalar(select(Connection)) is None


async def test_create_connection_warnings(
    client: httpx.AsyncClient, fake_gitlab: FakeGitLab
) -> None:
    fake_gitlab.token_info = {
        "name": "t",
        "scopes": ["api"],
        "active": True,
        "expires_at": (NOW.date() + timedelta(days=3)).isoformat(),
    }
    await login(client)

    warnings = (await create_connection(client))["warnings"]

    assert any("full api scope" in w for w in warnings)
    assert any(str(date(2026, 10, 27)) in w for w in warnings)


async def test_old_gitlab_without_token_introspection(
    client: httpx.AsyncClient, fake_gitlab: FakeGitLab
) -> None:
    fake_gitlab.token_info = 404
    await login(client)
    assert "Could not verify" in (await create_connection(client))["warnings"][0]


async def test_rejects_non_http_base_url(client: httpx.AsyncClient) -> None:
    await login(client)
    body = {**NEW_CONNECTION, "base_url": "file:///etc/passwd"}
    assert (await client.post("/api/connections", json=body)).status_code == 422


# --- projects ---------------------------------------------------------------------------------


async def test_search_and_add_project(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await login(client)
    connection = await create_connection(client)
    base = f"/api/connections/{connection['id']}"

    [found] = (await client.get(f"{base}/gitlab-projects", params={"search": "g/"})).json()
    assert (found["path_with_namespace"], found["already_added"]) == ("g/p", False)

    response = await client.post(f"{base}/projects", json={"project": "g/p"})
    assert response.status_code == 201
    added = response.json()
    assert (added["gitlab_project_id"], added["default_branch"]) == (PROJECT_ID, "main")

    [found] = (await client.get(f"{base}/gitlab-projects")).json()
    assert found["already_added"] is True
    duplicate = await client.post(f"{base}/projects", json={"project": PROJECT_ID})
    assert duplicate.status_code == 409

    project = await session.get(Project, added["id"])
    assert project.last_polled_at is None  # worker will backfill


async def test_add_unknown_project(client: httpx.AsyncClient) -> None:
    await login(client)
    connection = await create_connection(client)
    response = await client.post(
        f"/api/connections/{connection['id']}/projects", json={"project": "nope/nope"}
    )
    assert response.status_code == 404


async def test_delete_connection_cascades(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await login(client)
    connection = await create_connection(client)
    added = (
        await client.post(f"/api/connections/{connection['id']}/projects", json={"project": "g/p"})
    ).json()
    session.add(
        Pipeline(
            project_id=added["id"],
            gitlab_pipeline_id=1,
            status="success",
            ref="main",
            sha="a" * 40,
            web_url="https://gitlab.example.com/p",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    await session.commit()

    response = await client.delete(f"/api/connections/{connection['id']}")

    assert response.status_code == 204
    session.expire_all()
    assert await session.scalar(select(Connection)) is None
    assert await session.scalar(select(Project)) is None
    assert await session.scalar(select(Pipeline)) is None


async def test_delete_project(client: httpx.AsyncClient) -> None:
    await login(client)
    connection = await create_connection(client)
    added = (
        await client.post(f"/api/connections/{connection['id']}/projects", json={"project": "g/p"})
    ).json()

    assert (await client.delete(f"/api/projects/{added['id']}")).status_code == 204
    assert (await client.delete(f"/api/projects/{added['id']}")).status_code == 404
    assert (await client.get("/api/connections")).json()[0]["project_count"] == 0
