"""Managing GitLab connections and tracked projects. Admin only, disabled in demo mode."""

from collections.abc import Awaitable
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pipepulse.auth import require_admin
from pipepulse.crypto import TokenDecryptionError, token_hint
from pipepulse.deps import CipherDep, GitLabFactoryDep, NowDep, SessionDep
from pipepulse.gitlab import GitLabAuthError, GitLabError, GitLabNotFoundError
from pipepulse.gitlab.client import GitLabClient
from pipepulse.models import Connection, Project

router = APIRouter(prefix="/api", tags=["connections"], dependencies=[Depends(require_admin)])

READ_SCOPES = {"read_api", "api"}
EXPIRY_WARNING = timedelta(days=14)


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    token: str = Field(min_length=8, max_length=255)


class ConnectionOut(BaseModel):
    id: int
    name: str
    base_url: str
    token_masked: str
    created_at: datetime
    project_count: int


class ConnectionCreated(ConnectionOut):
    warnings: list[str]


class GitLabProjectOut(BaseModel):
    gitlab_project_id: int
    name: str
    path_with_namespace: str
    web_url: str
    already_added: bool


class ProjectAdd(BaseModel):
    # Numeric id or "group/subgroup/project" path.
    project: int | str


class ProjectOut(BaseModel):
    id: int
    connection_id: int | None
    gitlab_project_id: int
    name: str
    path_with_namespace: str
    web_url: str
    default_branch: str | None


@router.get("/connections")
async def list_connections(session: SessionDep) -> list[ConnectionOut]:
    rows = await session.execute(
        select(Connection, func.count(Project.id))
        .outerjoin(Project)
        .group_by(Connection.id)
        .order_by(Connection.name)
    )
    return [_connection_out(connection, projects) for connection, projects in rows]


@router.post("/connections", status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreate,
    session: SessionDep,
    cipher: CipherDep,
    gitlab: GitLabFactoryDep,
    now: NowDep,
) -> ConnectionCreated:
    base_url = str(body.base_url).rstrip("/")
    async with gitlab(base_url, body.token) as client:
        warnings = await _validate_token(client, now.date())

    connection = Connection(
        name=body.name,
        base_url=base_url,
        token_encrypted=cipher.encrypt(body.token),
        token_hint=token_hint(body.token),
    )
    session.add(connection)
    await session.commit()
    await session.refresh(connection)  # created_at is set by the database
    return ConnectionCreated(**_connection_out(connection, 0).model_dump(), warnings=warnings)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: int, session: SessionDep) -> None:
    """Deletes the stored token and all its projects' history. Revoke the token in GitLab too."""
    connection = await _get_connection(session, connection_id)
    await session.delete(connection)
    await session.commit()


@router.get("/connections/{connection_id}/gitlab-projects")
async def search_gitlab_projects(
    connection_id: int,
    session: SessionDep,
    cipher: CipherDep,
    gitlab: GitLabFactoryDep,
    search: str = "",
) -> list[GitLabProjectOut]:
    connection = await _get_connection(session, connection_id)
    async with gitlab(connection.base_url, _decrypt(cipher, connection)) as client:
        found = await _gitlab_call(client.search_projects(search))
    added = set(
        await session.scalars(
            select(Project.gitlab_project_id).where(Project.connection_id == connection_id)
        )
    )
    return [
        GitLabProjectOut(
            gitlab_project_id=p.id,
            name=p.name,
            path_with_namespace=p.path_with_namespace,
            web_url=p.web_url,
            already_added=p.id in added,
        )
        for p in found
    ]


@router.post("/connections/{connection_id}/projects", status_code=status.HTTP_201_CREATED)
async def add_project(
    connection_id: int,
    body: ProjectAdd,
    session: SessionDep,
    cipher: CipherDep,
    gitlab: GitLabFactoryDep,
) -> ProjectOut:
    connection = await _get_connection(session, connection_id)
    async with gitlab(connection.base_url, _decrypt(cipher, connection)) as client:
        try:
            found = await client.get_project(body.project)
        except GitLabNotFoundError as exc:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Project not found, or the token can't access it"
            ) from exc
        except GitLabError as exc:
            raise _upstream_error(exc) from exc

    # last_polled_at stays empty: the worker backfills history on its next cycle.
    project = Project(
        connection_id=connection.id,
        gitlab_project_id=found.id,
        path_with_namespace=found.path_with_namespace,
        name=found.name,
        web_url=found.web_url,
        default_branch=found.default_branch,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Project is already tracked") from exc
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, session: SessionDep) -> None:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    await session.delete(project)
    await session.commit()


async def _validate_token(client: GitLabClient, today: date) -> list[str]:
    """Reject unusable tokens; return warnings for usable but questionable ones."""
    try:
        info = await client.get_token_info()
    except GitLabAuthError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "GitLab rejected the token (invalid, expired or revoked)"
        ) from exc
    except GitLabNotFoundError:
        # GitLab < 15.5 has no token self-inspection; fall back to proving the token works.
        await _gitlab_call(client.get_current_user())
        return ["Could not verify token scopes on this GitLab version; read_api is recommended"]
    except GitLabError as exc:
        raise _upstream_error(exc) from exc

    if not info.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token is not active")
    if not READ_SCOPES & set(info.scopes):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Token needs the read_api scope (has: {', '.join(info.scopes) or 'none'})",
        )
    warnings = []
    if "api" in info.scopes:
        warnings.append("Token has the full api scope; read_api is enough for pipepulse")
    if info.expires_at and info.expires_at - today <= EXPIRY_WARNING:
        warnings.append(f"Token expires on {info.expires_at.isoformat()}")
    return warnings


async def _gitlab_call[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except GitLabAuthError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "GitLab rejected the stored token; re-add the connection"
        ) from exc
    except GitLabError as exc:
        raise _upstream_error(exc) from exc


def _upstream_error(exc: GitLabError) -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitLab request failed: {exc}")


async def _get_connection(session: SessionDep, connection_id: int) -> Connection:
    connection = await session.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return connection


def _decrypt(cipher: CipherDep, connection: Connection) -> str:
    try:
        return cipher.decrypt(connection.token_encrypted)
    except TokenDecryptionError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Stored token can't be decrypted with the current key; re-add the connection",
        ) from exc


def _connection_out(connection: Connection, project_count: int) -> ConnectionOut:
    return ConnectionOut(
        id=connection.id,
        name=connection.name,
        base_url=connection.base_url,
        token_masked=f"****{connection.token_hint}",
        created_at=connection.created_at,
        project_count=project_count,
    )
