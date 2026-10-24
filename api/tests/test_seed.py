from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from pipepulse.models import Connection, Job, Pipeline, Project
from pipepulse.seed.generator import seed_demo
from pipepulse.seed.profiles import PROFILES

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
DAYS = 30


async def load(session: AsyncSession) -> dict[str, list[Pipeline]]:
    projects = await session.scalars(
        select(Project)
        .where(Project.connection_id.is_(None))
        .options(selectinload(Project.pipelines).selectinload(Pipeline.failed_jobs))
    )
    return {p.name: sorted(p.pipelines, key=lambda pl: pl.created_at) for p in projects.unique()}


async def test_seed_is_deterministic(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    snapshots = []
    for _ in range(2):
        async with sessionmaker() as session:
            await seed_demo(session, now=NOW, days=DAYS)
            await session.commit()
            snapshots.append(
                {
                    name: [(p.gitlab_pipeline_id, p.status, p.duration_s, p.sha) for p in runs]
                    for name, runs in (await load(session)).items()
                }
            )
    assert snapshots[0] == snapshots[1]


async def test_seed_replaces_only_demo_projects(session: AsyncSession) -> None:
    connection = Connection(
        name="real", base_url="https://gitlab.com", token_encrypted=b"x", token_hint="abcd"
    )
    real = Project(
        connection=connection,
        gitlab_project_id=1001,  # same id as a demo project on purpose
        path_with_namespace="me/real",
        name="real",
        web_url="https://gitlab.com/me/real",
    )
    session.add(real)
    await session.commit()

    first = await seed_demo(session, now=NOW, days=DAYS)
    second = await seed_demo(session, now=NOW, days=DAYS)
    await session.commit()

    assert first == second
    assert len(await load(session)) == len(PROFILES)
    assert await session.get(Project, real.id) is not None


async def test_seed_data_is_consistent(session: AsyncSession) -> None:
    await seed_demo(session, now=NOW, days=DAYS, trace_tail_lines=10)
    await session.commit()

    for name, runs in (await load(session)).items():
        ids = [p.gitlab_pipeline_id for p in runs]
        assert ids == sorted(ids), f"{name}: ids should grow with time"
        for p in runs:
            assert NOW - timedelta(days=DAYS) <= p.created_at <= p.updated_at <= NOW
            if p.status == "failed":
                [job] = p.failed_jobs
                assert job.trace_tail and len(job.trace_tail.split("\n")) <= 10
            else:
                assert p.failed_jobs == []
            if p.status == "running":
                assert p.finished_at is None and p.duration_s is None
            else:
                assert p.finished_at == p.started_at + timedelta(seconds=p.duration_s)


async def test_seed_tells_the_intended_stories(session: AsyncSession) -> None:
    await seed_demo(session, now=NOW, days=DAYS)
    await session.commit()
    data = await load(session)

    def main_runs(name: str) -> list[Pipeline]:
        return [p for p in data[name] if p.ref == "main"]

    # Active failure: newest main pipeline of web-frontend is red, with the log from the README.
    latest = main_runs("web-frontend")[-1]
    assert latest.status == "failed"
    jobs: list[Job] = latest.failed_jobs
    assert "Cannot find module './auth'" in jobs[0].trace_tail

    # Something is building right now.
    assert main_runs("api-service")[-1].status == "running"

    # payments-worker gets noticeably slower.
    def avg_success_duration(runs: list[Pipeline], since: datetime, until: datetime) -> float:
        return mean(
            p.duration_s for p in runs if p.status == "success" and since <= p.created_at < until
        )

    payments = data["payments-worker"]
    first_week = avg_success_duration(payments, NOW - timedelta(days=30), NOW - timedelta(days=23))
    last_week = avg_success_duration(payments, NOW - timedelta(days=7), NOW)
    assert last_week > first_week * 1.4

    # mobile-app is the flaky one.
    def success_rate(name: str) -> float:
        finished = [p for p in data[name] if p.status in ("success", "failed")]
        return sum(p.status == "success" for p in finished) / len(finished)

    assert success_rate("mobile-app") < min(success_rate(n) for n in data if n != "mobile-app")

    # data-pipeline has a long incident: a red streak on main lasting over a day.
    pipeline_runs = [p for p in main_runs("data-pipeline") if p.status in ("success", "failed")]
    longest, red_since = timedelta(0), None
    for p in pipeline_runs:
        if p.status == "failed":
            red_since = red_since or p.finished_at
        elif red_since:
            longest, red_since = max(longest, p.finished_at - red_since), None
    assert longest > timedelta(days=1)
