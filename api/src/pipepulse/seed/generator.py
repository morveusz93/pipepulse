"""Deterministic pipeline history generator for demo mode.

History is generated relative to `now`, so a fresh seed always looks current. The same `now`
and seed always produce identical data.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from itertools import count

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.models import Job, Pipeline, Project
from pipepulse.seed import failures as f
from pipepulse.seed.profiles import COMMIT_TITLES, PROFILES, ProjectProfile

WEB_BASE = "https://gitlab.example.com/acme"
DEFAULT_BRANCH = "main"
WORKDAY_HOURS = (8, 19)


@dataclass(frozen=True)
class SeedResult:
    projects: int
    pipelines: int
    failed_jobs: int


async def seed_demo(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    days: int = 30,
    trace_tail_lines: int = 50,
    seed: int = 42,
) -> SeedResult:
    """Replace all demo projects (those without a connection) with fresh generated history.

    Commits nothing — the caller owns the transaction.
    """
    now = now or datetime.now(UTC)
    await session.execute(delete(Project).where(Project.connection_id.is_(None)))

    pipeline_ids = count(2_840_000)
    job_ids = count(8_120_000_000)
    for profile in PROFILES:
        rng = random.Random(f"{seed}:{profile.name}")
        project = Project(
            gitlab_project_id=profile.gitlab_project_id,
            path_with_namespace=f"acme/{profile.name}",
            name=profile.name,
            web_url=f"{WEB_BASE}/{profile.name}",
            default_branch=DEFAULT_BRANCH,
            last_polled_at=now,
        )
        runs = _ProjectHistory(profile, rng, now, days, trace_tail_lines).generate()
        for pipeline in sorted(runs, key=lambda p: p.created_at):
            pipeline.gitlab_pipeline_id = next(pipeline_ids)
            pipeline.web_url = f"{project.web_url}/-/pipelines/{pipeline.gitlab_pipeline_id}"
            for job in pipeline.failed_jobs:
                job.gitlab_job_id = next(job_ids)
                job.web_url = f"{project.web_url}/-/jobs/{job.gitlab_job_id}"
            project.pipelines.append(pipeline)
        session.add(project)
    await session.flush()

    demo = Project.connection_id.is_(None)
    pipelines = await session.scalar(
        select(func.count()).select_from(Pipeline).join(Project).where(demo)
    )
    jobs = await session.scalar(
        select(func.count()).select_from(Job).join(Pipeline).join(Project).where(demo)
    )
    return SeedResult(projects=len(PROFILES), pipelines=pipelines or 0, failed_jobs=jobs or 0)


class _ProjectHistory:
    def __init__(
        self,
        profile: ProjectProfile,
        rng: random.Random,
        now: datetime,
        days: int,
        trace_tail_lines: int,
    ) -> None:
        self.profile = profile
        self.rng = rng
        self.now = now
        self.start = now - timedelta(days=days)
        self.trace_tail_lines = trace_tail_lines
        self._mr_iids = {branch: 120 + i * 17 for i, branch in enumerate(profile.branches)}

    def generate(self) -> list[Pipeline]:
        runs: list[Pipeline] = []
        day = self.start.date()
        while day <= self.now.date():
            runs.extend(self._day(day))
            day += timedelta(days=1)
        runs.extend(self._fixes(runs))

        if self.profile.failing_now:
            failed_at = self.now - timedelta(minutes=self.rng.uniform(25, 55))
            # Nothing newer on the default branch, so the failure is still "active".
            runs = [r for r in runs if r.ref != DEFAULT_BRANCH or r.created_at < failed_at]
            runs.append(self._run(failed_at, DEFAULT_BRANCH, "push", self.profile.failing_now))
        if self.profile.running_now:
            runs.append(self._running(self.now - timedelta(seconds=self.rng.uniform(60, 150))))
        return [r for r in runs if self.start <= r.created_at and r.updated_at <= self.now]

    def _fixes(self, runs: list[Pipeline]) -> list[Pipeline]:
        """A red default branch normally gets a fix commit within the hour.

        Incidents are the exception, which is what makes them stand out in MTTR.
        """
        fixes = []
        for run in runs:
            if run.ref != DEFAULT_BRANCH or run.status != "failed":
                continue
            if self._incident_failure(run.created_at, run.ref) is not None:
                continue
            fixed_at = run.finished_at + timedelta(minutes=self.rng.uniform(15, 90))
            fixes.append(self._run(fixed_at, DEFAULT_BRANCH, "push", may_fail=False))
        return fixes

    def _day(self, day) -> list[Pipeline]:
        weekend = day.weekday() >= 5
        expected = self.profile.runs_per_weekday * (self.profile.weekend_factor if weekend else 1)
        n = max(0, round(self.rng.gauss(expected, expected**0.5))) if expected else 0
        midnight = datetime.combine(day, time(), tzinfo=UTC)

        runs = []
        for _ in range(n):
            hour = self.rng.uniform(*WORKDAY_HOURS)
            created = midnight + timedelta(hours=hour)
            if self.rng.random() < self.profile.main_share:
                runs.append(self._run(created, DEFAULT_BRANCH, "push"))
            else:
                branch = self.rng.choice(self.profile.branches)
                if self.rng.random() < 0.7:
                    ref = f"refs/merge-requests/{self._mr_iids[branch]}/head"
                    runs.append(self._run(created, ref, "merge_request_event"))
                else:
                    runs.append(self._run(created, branch, "push"))

        if self.profile.scheduled_hour_utc is not None:
            created = midnight + timedelta(hours=self.profile.scheduled_hour_utc, seconds=4)
            runs.append(self._run(created, DEFAULT_BRANCH, "schedule"))
        return runs

    def _run(
        self,
        created: datetime,
        ref: str,
        source: str,
        failure: f.Failure | None = None,
        *,
        may_fail: bool = True,
    ) -> Pipeline:
        rng = self.rng
        duration = self._nominal_duration(created)
        status = "success"
        if failure is None:
            failure = self._incident_failure(created, ref)
        if failure is None and may_fail and rng.random() < self.profile.fail_rate:
            weighted = self.profile.failures
            failure = rng.choices([w[0] for w in weighted], [w[1] for w in weighted])[0]
        if failure is not None:
            status = "failed"
            duration = self._failed_duration(failure, duration)
        elif may_fail and rng.random() < 0.03:
            status = "canceled"
            duration = round(duration * rng.uniform(0.1, 0.6))

        queued = rng.uniform(1, 12) if rng.random() < 0.9 else rng.uniform(40, 240)
        started = created + timedelta(seconds=queued)
        finished = started + timedelta(seconds=duration)
        pipeline = Pipeline(
            status=status,
            ref=ref,
            sha=f"{rng.getrandbits(160):040x}",
            source=source,
            commit_title=rng.choice(COMMIT_TITLES),
            duration_s=duration,
            queued_duration_s=round(queued),
            created_at=created,
            started_at=started,
            finished_at=finished,
            updated_at=finished,
        )
        if failure is not None:
            pipeline.failed_jobs.append(self._job(failure, duration, finished))
        return pipeline

    def _running(self, created: datetime) -> Pipeline:
        started = created + timedelta(seconds=self.rng.uniform(2, 8))
        return Pipeline(
            status="running",
            ref=DEFAULT_BRANCH,
            sha=f"{self.rng.getrandbits(160):040x}",
            source="push",
            commit_title=self.rng.choice(COMMIT_TITLES),
            queued_duration_s=round((started - created).total_seconds()),
            created_at=created,
            started_at=started,
            updated_at=self.now,
        )

    def _nominal_duration(self, created: datetime) -> int:
        # Linear drift from 1.0 at the start of history to duration_drift today.
        progress = (created - self.start) / (self.now - self.start)
        drift = 1 + (self.profile.duration_drift - 1) * progress
        return round(self.profile.base_duration_s * drift * self.rng.lognormvariate(0, 0.12))

    def _failed_duration(self, failure: f.Failure, nominal: int) -> int:
        if failure.reason == "stuck_or_timeout_failure":
            return 3600 + round(self.rng.uniform(5, 40))
        if failure.reason == "runner_system_failure":
            return round(self.rng.uniform(15, 45))
        return round(nominal * self.rng.uniform(0.35, 0.85))

    def _incident_failure(self, created: datetime, ref: str) -> f.Failure | None:
        if ref != DEFAULT_BRANCH:
            return None
        for incident in self.profile.incidents:
            begins = self.now - timedelta(days=incident.start_days_ago)
            if begins <= created < begins + timedelta(hours=incident.hours):
                return incident.failure
        return None

    def _job(self, failure: f.Failure, pipeline_duration: int, finished: datetime) -> Job:
        return Job(
            name=failure.job,
            stage=failure.stage,
            status="failed",
            failure_reason=failure.reason,
            duration_s=round(pipeline_duration * self.rng.uniform(0.4, 0.9)),
            trace_tail="\n".join(failure.log.split("\n")[-self.trace_tail_lines :]),
            finished_at=finished,
        )
