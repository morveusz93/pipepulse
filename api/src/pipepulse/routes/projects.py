from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from pipepulse import stats
from pipepulse.deps import DaysQuery, NowDep, ScopeQuery, SessionDep
from pipepulse.models import Project
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
    session: SessionDep, now: NowDep, days: DaysQuery = 7, scope: ScopeQuery = "default"
) -> Summary:
    since = now - timedelta(days=days)
    latest_finished = await stats.latest_default_branch(session, finished_only=True)
    projects = await session.scalars(select(Project.id))
    return Summary(
        window_days=days,
        projects=len(projects.all()),
        active_failures=sum(p.status == "failed" for p in latest_finished.values()),
        running=await stats.running_count(session),
        stats=await stats.window_stats(session, since, now, scope),
    )


@router.get("/projects")
async def list_projects(
    session: SessionDep, now: NowDep, days: DaysQuery = 7, scope: ScopeQuery = "default"
) -> list[ProjectRow]:
    return await _project_rows(session, now, days, scope)


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
) -> list[ProjectRow]:
    query = select(Project).order_by(Project.name)
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
            is_demo=p.connection_id is None,
            last_polled_at=p.last_polled_at,
            latest=PipelineBrief.model_validate(latest[p.id]) if p.id in latest else None,
            active_failure=p.id in latest_finished and latest_finished[p.id].status == "failed",
            pulse=pulses.get(p.id, []),
            stats=window.get(p.id, WindowStats()),
        )
        for p in projects
    ]
