"""Demo projects. Each one tells a different story on the dashboard."""

from dataclasses import dataclass, field

from pipepulse.seed import failures as f


@dataclass(frozen=True)
class Incident:
    """A window where every pipeline on the default branch fails with the same error."""

    start_days_ago: float
    hours: float
    failure: f.Failure


@dataclass(frozen=True)
class ProjectProfile:
    name: str
    gitlab_project_id: int
    runs_per_weekday: float
    base_duration_s: int
    fail_rate: float
    # Weighted failures for random (non-incident) red pipelines.
    failures: tuple[tuple[f.Failure, int], ...]
    # Duration multiplier reached by today, ramping linearly from 1.0 at the start of history.
    duration_drift: float = 1.0
    weekend_factor: float = 0.15
    main_share: float = 0.4
    scheduled_hour_utc: int | None = None
    incidents: tuple[Incident, ...] = ()
    # The newest default-branch pipeline is red — shows up as an active failure.
    failing_now: f.Failure | None = None
    running_now: bool = False
    branches: tuple[str, ...] = field(default=())


PROFILES: tuple[ProjectProfile, ...] = (
    ProjectProfile(
        name="api-service",
        gitlab_project_id=1001,
        runs_per_weekday=14,
        base_duration_s=228,
        fail_rate=0.05,
        failures=((f.PYTEST_ASSERTION, 6), (f.RUNNER_TIMEOUT, 1), (f.HELM_TIMEOUT, 2)),
        running_now=True,
        branches=("feat/refund-limits", "fix/idempotency-keys", "chore/bump-fastapi"),
    ),
    ProjectProfile(
        name="web-frontend",
        gitlab_project_id=1002,
        runs_per_weekday=18,
        base_duration_s=362,
        fail_rate=0.12,
        failures=((f.E2E_TIMEOUT, 6), (f.ESLINT, 3), (f.DOCKER_BUILD, 2), (f.RUNNER_SYSTEM, 1)),
        failing_now=f.E2E_MISSING_MODULE,
        branches=("feat/checkout-v2", "feat/dark-mode", "fix/cart-rounding", "refactor/auth"),
    ),
    ProjectProfile(
        name="infra-deploy",
        gitlab_project_id=1003,
        runs_per_weekday=4,
        base_duration_s=75,
        fail_rate=0.03,
        failures=((f.TERRAFORM_PLAN, 1),),
        weekend_factor=0.0,
        main_share=0.6,
        branches=("feat/eks-1-31", "chore/rotate-certs"),
    ),
    ProjectProfile(
        name="payments-worker",
        gitlab_project_id=1004,
        runs_per_weekday=9,
        base_duration_s=245,
        fail_rate=0.07,
        failures=((f.GO_RACE, 3), (f.RUNNER_TIMEOUT, 1)),
        # Builds got ~75% slower over the month — the trend chart should make this obvious.
        duration_drift=1.75,
        branches=("feat/settlement-batching", "fix/retry-backoff"),
    ),
    ProjectProfile(
        name="mobile-app",
        gitlab_project_id=1005,
        runs_per_weekday=7,
        base_duration_s=720,
        fail_rate=0.22,
        failures=((f.UI_TEST_FLAKY, 5), (f.GRADLE_COMPILE, 2), (f.RUNNER_SYSTEM, 1)),
        weekend_factor=0.05,
        branches=("feat/orders-redesign", "feat/biometric-login", "fix/push-tokens"),
    ),
    ProjectProfile(
        name="data-pipeline",
        gitlab_project_id=1006,
        runs_per_weekday=3,
        base_duration_s=540,
        fail_rate=0.04,
        failures=((f.DBT_MODEL, 1),),
        weekend_factor=0.0,
        main_share=0.5,
        scheduled_hour_utc=4,
        # A schema change upstream broke the nightly models for ~2 days — the MTTR outlier.
        incidents=(Incident(start_days_ago=9.2, hours=46, failure=f.DBT_MODEL),),
        branches=("feat/cohort-retention", "fix/orders-discount-column"),
    ),
)

COMMIT_TITLES: tuple[str, ...] = (
    "fix: handle empty cart on checkout",
    "feat: add retry with jitter to webhook sender",
    "chore(deps): bump httpx to 0.28.1",
    "refactor: extract pricing rules into module",
    "test: cover refund edge cases",
    "fix: race in settlement batcher flush",
    "ci: cache pnpm store between jobs",
    "feat: paginate orders endpoint",
    "docs: update local setup instructions",
    "fix: timezone bug in daily report",
    "perf: add index on orders(created_at)",
    "feat: dark mode for dashboard",
    "chore: remove unused feature flags",
    "fix: null discount in order totals",
    "feat: export invoices as CSV",
    "build: switch base image to distroless",
    "fix: flaky checkout e2e selector",
    "feat: biometric login on Android",
    "chore(deps): update kotlin to 2.0.21",
    'revert: "feat: paginate orders endpoint"',
)
