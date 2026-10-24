"""Subset of GitLab REST API v4 payloads that pipepulse consumes. Unknown fields are ignored."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _GitLabModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class GitLabProject(_GitLabModel):
    id: int
    name: str
    path_with_namespace: str
    web_url: str
    default_branch: str | None = None


class GitLabPipeline(_GitLabModel):
    """Item from the pipelines list endpoint — no timings, see GitLabPipelineDetail."""

    id: int
    status: str
    ref: str
    sha: str
    source: str | None = None
    web_url: str
    created_at: datetime
    updated_at: datetime


class GitLabPipelineDetail(GitLabPipeline):
    duration: int | None = None
    queued_duration: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class GitLabJob(_GitLabModel):
    id: int
    name: str
    stage: str
    status: str
    failure_reason: str | None = None
    duration: float | None = None
    web_url: str
    finished_at: datetime | None = None


class GitLabCommit(_GitLabModel):
    id: str
    short_id: str
    title: str


class GitLabTokenInfo(_GitLabModel):
    name: str
    scopes: list[str]
    active: bool = True
    expires_at: date | None = None


class GitLabUser(_GitLabModel):
    id: int
    username: str
