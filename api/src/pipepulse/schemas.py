"""API response models."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# "default": only the project's default branch (health signal — a red MR is normal work).
# "all": every ref.
Scope = Literal["default", "all"]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PipelineBrief(_Out):
    id: int
    gitlab_pipeline_id: int
    status: str
    ref: str
    duration_s: int | None
    created_at: datetime
    finished_at: datetime | None
    web_url: str


class PulseRun(_Out):
    id: int
    status: str
    duration_s: int | None
    created_at: datetime


class WindowStats(BaseModel):
    runs: int = 0
    succeeded: int = 0
    failed: int = 0
    # succeeded / (succeeded + failed); canceled and running runs don't count either way.
    success_rate: float | None = None
    avg_duration_s: float | None = None


class ProjectRow(_Out):
    id: int
    name: str
    path_with_namespace: str
    web_url: str
    default_branch: str | None
    is_demo: bool
    last_polled_at: datetime | None
    # Dropped from PIPEPULSE_PROJECTS: no longer polled, history kept until deleted.
    removed_at: datetime | None
    latest: PipelineBrief | None
    # Newest finished default-branch pipeline is red.
    active_failure: bool
    pulse: list[PulseRun]
    stats: WindowStats


class Summary(BaseModel):
    window_days: int
    projects: int
    active_failures: int
    # Pipelines not finished yet: running, pending or otherwise queued.
    running: int
    stats: WindowStats


class TrendPoint(BaseModel):
    day: date
    runs: int
    succeeded: int
    failed: int
    success_rate: float | None
    avg_duration_s: float | None
    p90_duration_s: float | None


class Incident(BaseModel):
    """A red streak on the default branch: first failure until the next success."""

    failed_at: datetime
    recovered_at: datetime | None
    duration_s: float | None


class Mttr(BaseModel):
    incidents: int
    recovered: int
    avg_s: float | None
    median_s: float | None
    max_s: float | None
    # Set while the default branch is still red.
    open_since: datetime | None
    history: list[Incident]


class ProjectStats(BaseModel):
    window_days: int
    scope: Scope
    current: WindowStats
    # Same-length window right before the current one, for deltas ("+12% slower").
    previous: WindowStats
    mttr: Mttr


class JobOut(_Out):
    id: int
    gitlab_job_id: int
    name: str
    stage: str
    status: str
    failure_reason: str | None
    duration_s: int | None
    web_url: str
    finished_at: datetime | None
    has_log: bool


class PipelineOut(PipelineBrief):
    project_id: int
    project_name: str
    sha: str
    source: str | None
    commit_title: str | None
    queued_duration_s: int | None
    started_at: datetime | None
    failed_jobs: list[JobOut]


class PipelinePage(BaseModel):
    items: list[PipelineOut]
    total: int
    limit: int
    offset: int


class JobLog(BaseModel):
    job: JobOut
    pipeline_id: int
    # Last N lines of the trace, ANSI codes preserved. None if GitLab didn't give us the log.
    log: str | None
