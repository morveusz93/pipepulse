"""Prometheus metrics, computed from the stored pipeline history at scrape time.

Served at /metrics, outside /api, so the public Ingress (which only routes /api and the
dashboard) never exposes it; scrape the API service from inside the cluster. Numbers match the
dashboard: default branches, projects removed from the configuration left out.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse import stats
from pipepulse.deps import NowDep, SessionDep
from pipepulse.models import Pipeline, Project

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=Response)
async def metrics(
    session: SessionDep,
    now: NowDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> Response:
    since = now - timedelta(days=days)
    window = f"{days}d"
    projects = list(await session.scalars(select(Project).where(Project.removed_at.is_(None))))
    window_stats = await stats.window_stats_by_project(session, since, now, "default")
    latest = await stats.latest_default_branch(session, finished_only=True)
    p90 = await _p90_by_project(session, since, now)
    running = await _running_by_project(session)

    registry = CollectorRegistry()
    by_project = ["project"]
    by_window = ["project", "window"]

    def gauge(name: str, doc: str, labels: list[str]) -> Gauge:
        return Gauge(name, doc, labels, registry=registry)

    failing = gauge(
        "pipepulse_project_failing",
        "1 if the newest finished default-branch pipeline failed",
        by_project,
    )
    running_g = gauge("pipepulse_project_running_pipelines", "Pipelines in progress", by_project)
    pipelines = gauge(
        "pipepulse_project_pipelines",
        "Default-branch pipelines created in the window, by status",
        ["project", "window", "status"],
    )
    success = gauge(
        "pipepulse_project_success_ratio",
        "Succeeded / (succeeded + failed) on the default branch",
        by_window,
    )
    avg = gauge(
        "pipepulse_project_duration_avg_seconds",
        "Average duration of successful default-branch pipelines",
        by_window,
    )
    p90_g = gauge(
        "pipepulse_project_duration_p90_seconds",
        "90th percentile duration of successful default-branch pipelines",
        by_window,
    )
    mttr = gauge(
        "pipepulse_project_mttr_median_seconds",
        "Median time from a default-branch failure to the next green pipeline",
        by_window,
    )
    polled = gauge(
        "pipepulse_project_last_polled_timestamp_seconds",
        "When the worker last synced the project (alert on staleness)",
        by_project,
    )

    for project in projects:
        name = project.path_with_namespace
        failing.labels(name).set(
            1 if getattr(latest.get(project.id), "status", None) == "failed" else 0
        )
        running_g.labels(name).set(running.get(project.id, 0))
        if project.last_polled_at:
            polled.labels(name).set(project.last_polled_at.timestamp())

        window_stat = window_stats.get(project.id)
        if window_stat:
            pipelines.labels(name, window, "success").set(window_stat.succeeded)
            pipelines.labels(name, window, "failed").set(window_stat.failed)
            pipelines.labels(name, window, "other").set(
                window_stat.runs - window_stat.succeeded - window_stat.failed
            )
            if window_stat.success_rate is not None:
                success.labels(name, window).set(window_stat.success_rate)
            if window_stat.avg_duration_s is not None:
                avg.labels(name, window).set(window_stat.avg_duration_s)
        if project.id in p90:
            p90_g.labels(name, window).set(p90[project.id])

        project_mttr = await stats.mttr(session, project, since)
        if project_mttr.median_s is not None:
            mttr.labels(name, window).set(project_mttr.median_s)

    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


async def _p90_by_project(
    session: AsyncSession, since: datetime, until: datetime
) -> dict[int, float]:
    p90 = (
        func.percentile_cont(0.9)
        .within_group(cast(Pipeline.duration_s, Float))
        .filter(Pipeline.status == "success")
    )
    rows = await session.execute(
        select(Pipeline.project_id, p90)
        .join(Project)
        .where(Pipeline.created_at >= since, Pipeline.created_at < until, stats.on_default_branch())
        .group_by(Pipeline.project_id)
    )
    return {project_id: float(value) for project_id, value in rows if value is not None}


async def _running_by_project(session: AsyncSession) -> dict[int, int]:
    rows = await session.execute(
        select(Pipeline.project_id, func.count())
        .where(Pipeline.status.in_(stats.ACTIVE_STATUSES))
        .group_by(Pipeline.project_id)
    )
    return dict(rows.all())
