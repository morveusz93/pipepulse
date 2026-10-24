"""Aggregates computed on read from pipeline history."""

from datetime import datetime, timedelta
from statistics import mean, median

from sqlalchemy import ColumnElement, Float, cast, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.models import Pipeline, Project
from pipepulse.schemas import Incident, Mttr, PulseRun, Scope, TrendPoint, WindowStats

FALLBACK_BRANCH = "main"
ACTIVE_STATUSES = ("created", "waiting_for_resource", "preparing", "pending", "running")
PULSE_LENGTH = 20


def on_default_branch() -> ColumnElement[bool]:
    """Requires Project to be joined."""
    return Pipeline.ref == func.coalesce(Project.default_branch, FALLBACK_BRANCH)


def _scoped(scope: Scope) -> list[ColumnElement[bool]]:
    return [on_default_branch()] if scope == "default" else []


def _stats_columns():
    return (
        func.count().label("runs"),
        func.count().filter(Pipeline.status == "success").label("succeeded"),
        func.count().filter(Pipeline.status == "failed").label("failed"),
        func.avg(Pipeline.duration_s).filter(Pipeline.status == "success").label("avg_duration"),
    )


def _to_stats(runs: int, succeeded: int, failed: int, avg_duration: float | None) -> WindowStats:
    decided = succeeded + failed
    return WindowStats(
        runs=runs,
        succeeded=succeeded,
        failed=failed,
        success_rate=succeeded / decided if decided else None,
        avg_duration_s=float(avg_duration) if avg_duration is not None else None,
    )


async def window_stats_by_project(
    session: AsyncSession, since: datetime, until: datetime, scope: Scope
) -> dict[int, WindowStats]:
    rows = await session.execute(
        select(Pipeline.project_id, *_stats_columns())
        .join(Project)
        .where(Pipeline.created_at >= since, Pipeline.created_at < until, *_scoped(scope))
        .group_by(Pipeline.project_id)
    )
    return {project_id: _to_stats(*values) for project_id, *values in rows}


async def window_stats(
    session: AsyncSession,
    since: datetime,
    until: datetime,
    scope: Scope,
    project_id: int | None = None,
) -> WindowStats:
    stmt = (
        select(*_stats_columns())
        .join(Project)
        .where(Pipeline.created_at >= since, Pipeline.created_at < until, *_scoped(scope))
    )
    if project_id is not None:
        stmt = stmt.where(Pipeline.project_id == project_id)
    return _to_stats(*(await session.execute(stmt)).one())


async def latest_default_branch(
    session: AsyncSession, *, finished_only: bool
) -> dict[int, Pipeline]:
    """Newest default-branch pipeline per project (DISTINCT ON)."""
    stmt = (
        select(Pipeline)
        .join(Project)
        .where(on_default_branch())
        .ext(distinct_on(Pipeline.project_id))
        .order_by(Pipeline.project_id, Pipeline.created_at.desc(), Pipeline.id.desc())
    )
    if finished_only:
        stmt = stmt.where(Pipeline.status.in_(("success", "failed")))
    return {p.project_id: p for p in await session.scalars(stmt)}


async def pulses(session: AsyncSession, scope: Scope) -> dict[int, list[PulseRun]]:
    """Last PULSE_LENGTH pipelines per project, oldest first (left to right on the bar)."""
    position = (
        func.row_number()
        .over(partition_by=Pipeline.project_id, order_by=Pipeline.created_at.desc())
        .label("position")
    )
    ranked = (
        select(
            Pipeline.id,
            Pipeline.project_id,
            Pipeline.status,
            Pipeline.duration_s,
            Pipeline.created_at,
            position,
        )
        .join(Project)
        .where(*_scoped(scope))
        .subquery()
    )
    rows = await session.execute(
        select(ranked)
        .where(ranked.c.position <= PULSE_LENGTH)
        .order_by(ranked.c.project_id, ranked.c.created_at)
    )
    result: dict[int, list[PulseRun]] = {}
    for row in rows:
        result.setdefault(row.project_id, []).append(PulseRun.model_validate(row))
    return result


async def running_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(Pipeline).where(Pipeline.status.in_(ACTIVE_STATUSES))
    return await session.scalar(stmt) or 0


async def daily_trend(
    session: AsyncSession, project_id: int, since: datetime, until: datetime, scope: Scope
) -> list[TrendPoint]:
    """One point per UTC day in [since, until), empty days included so charts don't skip."""
    day = func.date(func.timezone("UTC", Pipeline.created_at)).label("day")
    per_day = (
        select(
            day,
            *_stats_columns(),
            func.percentile_cont(0.9)
            .within_group(cast(Pipeline.duration_s, Float))
            .filter(Pipeline.status == "success")
            .label("p90"),
        )
        .join(Project)
        .where(
            Pipeline.project_id == project_id,
            Pipeline.created_at >= since,
            Pipeline.created_at < until,
            *_scoped(scope),
        )
        .group_by(day)
    )
    by_day = {row.day: row for row in await session.execute(per_day)}

    points = []
    current, last = since.date(), (until - timedelta(microseconds=1)).date()
    while current <= last:
        row = by_day.get(current)
        stats = _to_stats(*(row[1:5] if row else (0, 0, 0, None)))
        points.append(
            TrendPoint(
                day=current,
                **stats.model_dump(),
                p90_duration_s=float(row.p90) if row and row.p90 is not None else None,
            )
        )
        current += timedelta(days=1)
    return points


async def mttr(session: AsyncSession, project: Project, since: datetime) -> Mttr:
    """Mean time to recovery on the default branch.

    An incident starts at the first failure after a success (or window start) and ends when the
    next pipeline on the same branch succeeds. Measured failure.finished_at -> success.finished_at.
    """
    branch = project.default_branch or FALLBACK_BRANCH
    rows = await session.execute(
        select(Pipeline.status, Pipeline.finished_at)
        .where(
            Pipeline.project_id == project.id,
            Pipeline.ref == branch,
            Pipeline.created_at >= since,
            Pipeline.status.in_(("success", "failed")),
            Pipeline.finished_at.is_not(None),
        )
        .order_by(Pipeline.created_at, Pipeline.id)
    )

    history: list[Incident] = []
    red_since: datetime | None = None
    for status, finished_at in rows:
        if status == "failed" and red_since is None:
            red_since = finished_at
        elif status == "success" and red_since is not None:
            duration = (finished_at - red_since).total_seconds()
            history.append(
                Incident(failed_at=red_since, recovered_at=finished_at, duration_s=duration)
            )
            red_since = None
    if red_since is not None:
        history.append(Incident(failed_at=red_since, recovered_at=None, duration_s=None))

    durations = [i.duration_s for i in history if i.duration_s is not None]
    return Mttr(
        incidents=len(history),
        recovered=len(durations),
        avg_s=mean(durations) if durations else None,
        median_s=median(durations) if durations else None,
        max_s=max(durations) if durations else None,
        open_since=red_since,
        history=list(reversed(history)),
    )
