from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.models import Job, Pipeline, Project
from pipepulse.sync import SyncOptions, sync_project
from tests.fake_gitlab import PROJECT_ID, FakeGitLab

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
OPTIONS = SyncOptions(
    backfill_days=30, trace_tail_lines=2, ignored_sources=frozenset({"duo_workflow"})
)


@pytest.fixture
async def project(session: AsyncSession) -> Project:
    project = Project(
        gitlab_project_id=PROJECT_ID,
        path_with_namespace="g/p",
        name="p",
        web_url="https://gitlab.example.com/g/p",
    )
    session.add(project)
    await session.commit()
    return project


async def sync(session: AsyncSession, gitlab: FakeGitLab, project: Project, now: datetime):
    async with gitlab.client() as client:
        result = await sync_project(session, client, project, OPTIONS, now=now)
    await session.commit()
    return result


async def pipelines(session: AsyncSession) -> dict[int, Pipeline]:
    rows = await session.scalars(select(Pipeline))
    return {p.gitlab_pipeline_id: p for p in rows}


async def jobs(session: AsyncSession) -> list[Job]:
    return list(await session.scalars(select(Job).order_by(Job.gitlab_job_id)))


async def test_initial_sync_backfills_window_and_stores_failures(
    session: AsyncSession, project: Project
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "success", NOW - timedelta(days=40))  # outside backfill window
    gitlab.add_pipeline(2, "success", NOW - timedelta(days=2), sha="b" * 40)
    gitlab.add_pipeline(3, "failed", NOW - timedelta(days=1), sha="b" * 40)
    gitlab.add_pipeline(4, "success", NOW - timedelta(hours=1), source="duo_workflow")
    gitlab.add_failed_job(3, 301, trace="line 1\nline 2\nERROR: boom")

    result = await sync(session, gitlab, project, NOW)

    stored = await pipelines(session)
    assert set(stored) == {2, 3}
    assert stored[3].commit_title == "commit bbbbbbbb"
    assert stored[3].duration_s == 120
    assert stored[3].queued_duration_s == 3
    assert gitlab.calls["commit"] == 1  # same sha fetched once
    [job] = await jobs(session)
    assert (job.gitlab_job_id, job.trace_tail, job.duration_s) == (301, "line 2\nERROR: boom", 30)
    assert project.last_polled_at == NOW
    assert result.pipelines_upserted == 2


async def test_unchanged_finished_pipelines_are_not_refetched(
    session: AsyncSession, project: Project
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "success", NOW - timedelta(minutes=3))
    await sync(session, gitlab, project, NOW)
    gitlab.calls.clear()

    # Still inside the poll overlap window, so GitLab returns it again.
    result = await sync(session, gitlab, project, NOW + timedelta(minutes=1))

    assert gitlab.calls["detail"] == 0
    assert result.pipelines_unchanged == 1


async def test_running_pipeline_is_updated_when_it_finishes(
    session: AsyncSession, project: Project
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "running", NOW - timedelta(minutes=1), duration=None)
    await sync(session, gitlab, project, NOW)

    gitlab.add_pipeline(1, "success", NOW + timedelta(minutes=2), duration=300)
    await sync(session, gitlab, project, NOW + timedelta(minutes=3))

    session.expire_all()
    stored = (await pipelines(session))[1]
    assert (stored.status, stored.duration_s) == ("success", 300)


async def test_retried_pipeline_that_went_green_drops_failed_jobs(
    session: AsyncSession, project: Project
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "failed", NOW - timedelta(minutes=1))
    gitlab.add_failed_job(1, 101, trace="boom")
    await sync(session, gitlab, project, NOW)
    assert len(await jobs(session)) == 1

    gitlab.add_pipeline(1, "success", NOW + timedelta(minutes=5))
    gitlab.failed_jobs.clear()
    await sync(session, gitlab, project, NOW + timedelta(minutes=6))

    assert await jobs(session) == []


async def test_missing_trace_keeps_job_without_log(session: AsyncSession, project: Project) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "failed", NOW - timedelta(minutes=1))
    gitlab.add_failed_job(1, 101, trace=None)

    result = await sync(session, gitlab, project, NOW)

    [job] = await jobs(session)
    assert job.trace_tail is None
    assert result.traces_missing == 1
