"""Synchronization of GitLab pipeline history into Postgres."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.gitlab import GitLabClient, GitLabError
from pipepulse.gitlab.schemas import GitLabPipelineDetail
from pipepulse.models import Job, Pipeline, Project

logger = logging.getLogger(__name__)

# Once a pipeline reaches one of these it won't change unless retried, which bumps updated_at.
TERMINAL_STATUSES = frozenset({"success", "failed", "canceled", "skipped"})
# Re-read a little before the last poll to absorb clock skew between us and GitLab.
POLL_OVERLAP = timedelta(minutes=5)


@dataclass(frozen=True)
class SyncOptions:
    backfill_days: int = 30
    trace_tail_lines: int = 50
    ignored_sources: frozenset[str] = frozenset()


@dataclass
class SyncResult:
    pipelines_upserted: int = 0
    pipelines_unchanged: int = 0
    failed_jobs_stored: int = 0
    traces_missing: int = 0


async def sync_project(
    session: AsyncSession,
    client: GitLabClient,
    project: Project,
    options: SyncOptions,
    *,
    now: datetime | None = None,
) -> SyncResult:
    """Fetch pipelines updated since the last poll and upsert them, with failed job logs.

    Commits nothing — the caller owns the transaction.
    """
    return await _ProjectSync(session, client, project, options).run(now or datetime.now(UTC))


class _ProjectSync:
    def __init__(
        self, session: AsyncSession, client: GitLabClient, project: Project, options: SyncOptions
    ) -> None:
        self.session = session
        self.client = client
        self.project = project
        self.options = options
        self.result = SyncResult()
        self._commit_titles: dict[str, str | None] = {}

    @property
    def _gitlab_id(self) -> int:
        return self.project.gitlab_project_id

    async def run(self, started: datetime) -> SyncResult:
        since = (
            self.project.last_polled_at - POLL_OVERLAP
            if self.project.last_polled_at
            else started - timedelta(days=self.options.backfill_days)
        )
        stored = await self._stored_pipelines(since)

        async for summary in self.client.iter_pipelines(self._gitlab_id, updated_after=since):
            if summary.source in self.options.ignored_sources:
                continue
            status, commit_title = stored.get(summary.id, (None, None))
            if status == summary.status and status in TERMINAL_STATUSES:
                self.result.pipelines_unchanged += 1
                continue

            detail = await self.client.get_pipeline(self._gitlab_id, summary.id)
            pipeline_id = await self._upsert_pipeline(
                detail, commit_title or await self._commit_title(detail.sha)
            )
            await self._replace_failed_jobs(pipeline_id, detail)
            self.result.pipelines_upserted += 1

        self.project.last_polled_at = started
        return self.result

    async def _stored_pipelines(self, since: datetime) -> dict[int, tuple[str, str | None]]:
        rows = await self.session.execute(
            select(Pipeline.gitlab_pipeline_id, Pipeline.status, Pipeline.commit_title).where(
                Pipeline.project_id == self.project.id, Pipeline.updated_at >= since
            )
        )
        return {gitlab_id: (status, title) for gitlab_id, status, title in rows}

    async def _commit_title(self, sha: str) -> str | None:
        if sha not in self._commit_titles:
            try:
                commit = await self.client.get_commit(self._gitlab_id, sha)
                self._commit_titles[sha] = commit.title
            except GitLabError as exc:
                # e.g. commit from a deleted branch or fork MR; the pipeline is still worth keeping.
                logger.info(
                    "No commit title for %s@%s: %s", self.project.path_with_namespace, sha[:8], exc
                )
                self._commit_titles[sha] = None
        return self._commit_titles[sha]

    async def _upsert_pipeline(self, detail: GitLabPipelineDetail, commit_title: str | None) -> int:
        values = {
            "status": detail.status,
            "ref": detail.ref,
            "sha": detail.sha,
            "source": detail.source,
            "commit_title": commit_title,
            "duration_s": detail.duration,
            "queued_duration_s": _seconds(detail.queued_duration),
            "web_url": detail.web_url,
            "created_at": detail.created_at,
            "started_at": detail.started_at,
            "finished_at": detail.finished_at,
            "updated_at": detail.updated_at,
        }
        stmt = (
            insert(Pipeline)
            .values(project_id=self.project.id, gitlab_pipeline_id=detail.id, **values)
            .on_conflict_do_update(index_elements=["project_id", "gitlab_pipeline_id"], set_=values)
            .returning(Pipeline.id)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _replace_failed_jobs(self, pipeline_id: int, detail: GitLabPipelineDetail) -> None:
        # A retried pipeline gets new job ids, and a pipeline that went green has no failures left.
        await self.session.execute(delete(Job).where(Job.pipeline_id == pipeline_id))
        if detail.status != "failed":
            return

        for job in await self.client.list_pipeline_jobs(self._gitlab_id, detail.id):
            try:
                trace = await self.client.get_job_trace_tail(
                    self._gitlab_id, job.id, lines=self.options.trace_tail_lines
                )
            except GitLabError as exc:
                # Traces need auth even on public projects, and may be erased or expired.
                logger.info(
                    "No trace for job %s in %s: %s", job.id, self.project.path_with_namespace, exc
                )
                trace = None
                self.result.traces_missing += 1

            self.session.add(
                Job(
                    pipeline_id=pipeline_id,
                    gitlab_job_id=job.id,
                    name=job.name,
                    stage=job.stage,
                    status=job.status,
                    failure_reason=job.failure_reason,
                    duration_s=_seconds(job.duration),
                    web_url=job.web_url,
                    trace_tail=trace,
                    finished_at=job.finished_at,
                )
            )
            self.result.failed_jobs_stored += 1
        await self.session.flush()


def _seconds(value: float | None) -> int | None:
    return round(value) if value is not None else None
