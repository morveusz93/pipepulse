from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from pipepulse.deps import SessionDep
from pipepulse.models import Job, Pipeline, Project
from pipepulse.schemas import JobLog, JobOut, PipelineOut, PipelinePage, Scope
from pipepulse.stats import on_default_branch

router = APIRouter(prefix="/api", tags=["pipelines"])

SORTS = {
    "-created_at": (Pipeline.created_at.desc(), Pipeline.id.desc()),
    "created_at": (Pipeline.created_at.asc(), Pipeline.id.asc()),
    "-duration": (Pipeline.duration_s.desc().nulls_last(), Pipeline.id.desc()),
    "duration": (Pipeline.duration_s.asc().nulls_last(), Pipeline.id.asc()),
}


@router.get("/pipelines")
async def list_pipelines(
    session: SessionDep,
    project_id: Annotated[list[int], Query()] = [],  # noqa: B006 — FastAPI copies defaults
    status_: Annotated[list[str], Query(alias="status")] = [],  # noqa: B006
    source: Annotated[list[str], Query()] = [],  # noqa: B006
    ref: str | None = None,
    scope: Scope = "all",
    since: datetime | None = None,
    until: datetime | None = None,
    sort: Literal["-created_at", "created_at", "-duration", "duration"] = "-created_at",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PipelinePage:
    filters = []
    if project_id:
        filters.append(Pipeline.project_id.in_(project_id))
    if status_:
        filters.append(Pipeline.status.in_(status_))
    if source:
        filters.append(Pipeline.source.in_(source))
    if ref is not None:
        filters.append(Pipeline.ref == ref)
    if scope == "default":
        filters.append(on_default_branch())
    if since is not None:
        filters.append(Pipeline.created_at >= since)
    if until is not None:
        filters.append(Pipeline.created_at < until)

    total = await session.scalar(
        select(func.count()).select_from(Pipeline).join(Project).where(*filters)
    )
    rows = await session.execute(
        select(Pipeline, Project.name)
        .join(Project)
        .where(*filters)
        .options(selectinload(Pipeline.failed_jobs))
        .order_by(*SORTS[sort])
        .limit(limit)
        .offset(offset)
    )
    return PipelinePage(
        items=[_pipeline_out(pipeline, name) for pipeline, name in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: int, session: SessionDep) -> PipelineOut:
    row = (
        await session.execute(
            select(Pipeline, Project.name)
            .join(Project)
            .where(Pipeline.id == pipeline_id)
            .options(selectinload(Pipeline.failed_jobs))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pipeline not found")
    return _pipeline_out(*row)


@router.get("/jobs/{job_id}/log")
async def get_job_log(job_id: int, session: SessionDep) -> JobLog:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobLog(job=_job_out(job), pipeline_id=job.pipeline_id, log=job.trace_tail)


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        gitlab_job_id=job.gitlab_job_id,
        name=job.name,
        stage=job.stage,
        status=job.status,
        failure_reason=job.failure_reason,
        duration_s=job.duration_s,
        web_url=job.web_url,
        finished_at=job.finished_at,
        has_log=job.trace_tail is not None,
    )


def _pipeline_out(pipeline: Pipeline, project_name: str) -> PipelineOut:
    return PipelineOut(
        id=pipeline.id,
        gitlab_pipeline_id=pipeline.gitlab_pipeline_id,
        project_id=pipeline.project_id,
        project_name=project_name,
        status=pipeline.status,
        ref=pipeline.ref,
        sha=pipeline.sha,
        source=pipeline.source,
        commit_title=pipeline.commit_title,
        duration_s=pipeline.duration_s,
        queued_duration_s=pipeline.queued_duration_s,
        web_url=pipeline.web_url,
        created_at=pipeline.created_at,
        started_at=pipeline.started_at,
        finished_at=pipeline.finished_at,
        failed_jobs=[_job_out(job) for job in pipeline.failed_jobs],
    )
