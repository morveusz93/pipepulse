from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import ColumnElement, exists, select

from pipepulse import stats
from pipepulse.config import Settings
from pipepulse.deps import DaysQuery, NowDep, ScopeQuery, SessionDep, SettingsDep
from pipepulse.models import Pipeline, Project
from pipepulse.schemas import (
    PipelineBrief,
    ProjectRow,
    ProjectStats,
    Summary,
    TrendPoint,
    WindowStats,
)

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/summary")
async def summary(
    session: SessionDep,
    now: NowDep,
    settings: SettingsDep,
    days: DaysQuery = 7,
    scope: ScopeQuery = "default",
) -> Summary:
    # Projects removed from the configuration are listed apart and stay out of the summary.
    since = now - timedelta(days=days)
    active = set(
        await session.scalars(
            select(Project.id).where(Project.removed_at.is_(None), *_listed(settings))
        )
    )
    latest_finished = await stats.latest_default_branch(session, finished_only=True)
    return Summary(
        window_days=days,
        projects=len(active),
        active_failures=sum(
            p.status == "failed" for pid, p in latest_finished.items() if pid in active
        ),
        running=await stats.running_count(session),
        stats=await stats.window_stats(session, since, now, scope, active_only=True),
    )


@router.get("/projects")
async def list_projects(
    session: SessionDep,
    now: NowDep,
    settings: SettingsDep,
    days: DaysQuery = 7,
    scope: ScopeQuery = "default",
) -> list[ProjectRow]:
    return await _project_rows(session, now, days, scope, where=_listed(settings))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    session: SessionDep,
    now: NowDep,
    days: DaysQuery = 7,
    scope: ScopeQuery = "default",
) -> ProjectRow:
    await _get_project_or_404(session, project_id)
    [row] = await _project_rows(session, now, days, scope, project_id=project_id)
    return row


@router.get("/projects/{project_id}/stats")
async def project_stats(
    project_id: int,
    session: SessionDep,
    now: NowDep,
    days: DaysQuery = 7,
    scope: ScopeQuery = "default",
) -> ProjectStats:
    project = await _get_project_or_404(session, project_id)
    since = now - timedelta(days=days)
    previous_since = since - timedelta(days=days)
    return ProjectStats(
        window_days=days,
        scope=scope,
        current=await stats.window_stats(session, since, now, scope, project_id),
        previous=await stats.window_stats(session, previous_since, since, scope, project_id),
        mttr=await stats.mttr(session, project, since),
    )


@router.get("/projects/{project_id}/trend")
async def project_trend(
    project_id: int,
    session: SessionDep,
    now: NowDep,
    days: DaysQuery = 30,
    scope: ScopeQuery = "default",
) -> list[TrendPoint]:
    await _get_project_or_404(session, project_id)
    # Whole UTC days, today included.
    since = datetime.combine(now.date() - timedelta(days=days - 1), time(), tzinfo=UTC)
    return await stats.daily_trend(session, project_id, since, now, scope)


class DeleteConfirmation(BaseModel):
    # The project's path, typed by the user: deleting history can't happen by a stray click.
    confirm: str


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, body: DeleteConfirmation, session: SessionDep) -> None:
    """Permanently delete a project removed from the configuration, with all its history.

    Only removed projects qualify, so the dashboard (which has no login) can never delete
    a project that's still being tracked.
    """
    project = await _get_project_or_404(session, project_id)
    if project.removed_at is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only projects removed from PIPEPULSE_PROJECTS can be deleted",
        )
    if body.confirm.strip() != project.path_with_namespace:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Confirmation doesn't match the project path"
        )
    await session.delete(project)
    await session.commit()


def _listed(settings: Settings) -> list[ColumnElement[bool]]:
    """Filters for project lists. When every accessible project is tracked (no explicit
    PIPEPULSE_PROJECTS), repositories that never ran a pipeline would only add empty rows."""
    if settings.project_paths:
        return []
    return [exists().where(Pipeline.project_id == Project.id)]


async def _get_project_or_404(session: SessionDep, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _project_rows(
    session: SessionDep,
    now: datetime,
    days: int,
    scope: ScopeQuery,
    *,
    project_id: int | None = None,
    where: list[ColumnElement[bool]] | None = None,
) -> list[ProjectRow]:
    query = select(Project).where(*(where or [])).order_by(Project.name)
    if project_id is not None:
        query = query.where(Project.id == project_id)
    projects = (await session.scalars(query)).all()

    window = await stats.window_stats_by_project(session, now - timedelta(days=days), now, scope)
    latest = await stats.latest_default_branch(session, finished_only=False)
    latest_finished = await stats.latest_default_branch(session, finished_only=True)
    pulses = await stats.pulses(session, scope)

    return [
        ProjectRow(
            id=p.id,
            name=p.name,
            path_with_namespace=p.path_with_namespace,
            web_url=p.web_url,
            default_branch=p.default_branch,
            is_demo=p.is_demo,
            removed_at=p.removed_at,
            last_polled_at=p.last_polled_at,
            latest=PipelineBrief.model_validate(latest[p.id]) if p.id in latest else None,
            active_failure=p.id in latest_finished and latest_finished[p.id].status == "failed",
            pulse=pulses.get(p.id, []),
            stats=window.get(p.id, WindowStats()),
        )
        for p in projects
    ]
