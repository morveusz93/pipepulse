from datetime import timedelta
from itertools import count

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pipepulse.models import Job, Pipeline, Project
from tests.conftest import NOW

_ids = count(1000)


def pipeline(
    project: Project,
    status: str,
    ago: timedelta,
    *,
    ref: str | None = None,
    duration: int | None = 100,
    log: str | None = "boom",
) -> Pipeline:
    created = NOW - ago
    finished = None if status == "running" else created + timedelta(seconds=duration or 0)
    p = Pipeline(
        project=project,
        gitlab_pipeline_id=next(_ids),
        status=status,
        ref=ref or project.default_branch,
        sha="a" * 40,
        source="push",
        duration_s=None if status == "running" else duration,
        web_url="https://gitlab.example.com/p",
        created_at=created,
        started_at=created,
        finished_at=finished,
        updated_at=finished or NOW,
    )
    if status == "failed":
        p.failed_jobs.append(
            Job(
                gitlab_job_id=next(_ids),
                name="test",
                stage="test",
                status="failed",
                web_url="https://gitlab.example.com/j",
                trace_tail=log,
            )
        )
    return p


def project(name: str, default_branch: str) -> Project:
    return Project(
        gitlab_project_id=next(_ids),
        path_with_namespace=f"g/{name}",
        name=name,
        web_url=f"https://gitlab.example.com/g/{name}",
        default_branch=default_branch,
    )


@pytest.fixture
async def data(session: AsyncSession) -> dict[str, Project]:
    alpha = project("alpha", default_branch="main")
    beta = project("beta", default_branch="develop")
    session.add_all(
        [
            pipeline(alpha, "success", timedelta(days=10), duration=999),  # outside 7d window
            pipeline(alpha, "success", timedelta(days=3), duration=100),
            pipeline(alpha, "failed", timedelta(days=2), duration=50),
            pipeline(alpha, "success", timedelta(days=1), duration=200),
            pipeline(alpha, "running", timedelta(minutes=5)),
            pipeline(alpha, "failed", timedelta(hours=1), ref="feature", log=None),  # not default
            pipeline(beta, "success", timedelta(days=1), duration=300),
            pipeline(beta, "failed", timedelta(hours=2), duration=60),
            pipeline(beta, "success", timedelta(hours=1), ref="main", duration=5),  # not default
        ]
    )
    await session.commit()
    return {"alpha": alpha, "beta": beta}


async def get(client: httpx.AsyncClient, url: str, **params) -> dict | list:
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_summary_uses_default_branches(client, data) -> None:
    body = await get(client, "/api/summary", days=7)

    assert body["projects"] == 2
    assert body["active_failures"] == 1  # beta: newest develop run failed
    assert body["running"] == 1
    # alpha main: 2 success, 1 failed, 1 running; beta develop: 1 success, 1 failed.
    assert body["stats"] == {
        "runs": 6,
        "succeeded": 3,
        "failed": 2,
        "success_rate": 0.6,
        "avg_duration_s": 200.0,
    }


async def test_summary_all_scope_includes_feature_branches(client, data) -> None:
    body = await get(client, "/api/summary", days=7, scope="all")
    assert (body["stats"]["runs"], body["stats"]["failed"]) == (8, 3)


async def test_project_rows(client, data) -> None:
    alpha, beta = await get(client, "/api/projects", days=7)

    assert alpha["name"] == "alpha"
    assert alpha["latest"]["status"] == "running"
    assert alpha["active_failure"] is False
    pulse = [r["status"] for r in alpha["pulse"]]
    assert pulse == ["success", "success", "failed", "success", "running"]
    assert alpha["stats"]["runs"] == 4
    assert alpha["is_demo"] is True

    assert beta["active_failure"] is True
    assert [r["status"] for r in beta["pulse"]] == ["success", "failed"]


async def test_project_stats_with_mttr(client, data) -> None:
    alpha = await get(client, f"/api/projects/{data['alpha'].id}/stats", days=7)

    assert alpha["current"]["runs"] == 4
    assert alpha["previous"]["runs"] == 1  # the 10-day-old run
    mttr = alpha["mttr"]
    # failed run finished at -2d+50s, recovered at -1d+200s
    assert mttr["incidents"] == mttr["recovered"] == 1
    assert mttr["avg_s"] == 86400 + 150
    assert mttr["open_since"] is None

    beta = await get(client, f"/api/projects/{data['beta'].id}/stats", days=7)
    assert beta["mttr"]["open_since"] == "2026-10-24T10:01:00Z"
    assert beta["mttr"]["avg_s"] is None


async def test_trend_has_every_day(client, data) -> None:
    trend = await get(client, f"/api/projects/{data['alpha'].id}/trend", days=4)

    assert [t["day"] for t in trend] == ["2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24"]
    assert [t["runs"] for t in trend] == [1, 1, 1, 1]
    assert [t["success_rate"] for t in trend] == [1.0, 0.0, 1.0, None]
    assert trend[0]["p90_duration_s"] == 100.0


async def test_list_pipelines_filters_and_sorts(client, data) -> None:
    page = await get(client, "/api/pipelines", status="failed")
    assert page["total"] == 3
    assert [p["created_at"] for p in page["items"]] == sorted(
        (p["created_at"] for p in page["items"]), reverse=True
    )

    page = await get(client, "/api/pipelines", project_id=data["beta"].id, scope="default")
    assert {p["ref"] for p in page["items"]} == {"develop"}

    page = await get(client, "/api/pipelines", sort="-duration", limit=2, offset=0)
    assert [p["duration_s"] for p in page["items"]] == [999, 300]
    assert page["total"] == 9


async def test_failed_jobs_and_log(client, data) -> None:
    page = await get(client, "/api/pipelines", status="failed", ref="feature")
    [job] = page["items"][0]["failed_jobs"]
    assert job["has_log"] is False

    page = await get(client, "/api/pipelines", status="failed", project_id=data["beta"].id)
    [job] = page["items"][0]["failed_jobs"]
    log = await get(client, f"/api/jobs/{job['id']}/log")
    assert log["log"] == "boom"
    assert log["pipeline_id"] == page["items"][0]["id"]


NOT_FOUND_URLS = [
    "/api/projects/0",
    "/api/projects/0/stats",
    "/api/projects/0/trend",
    "/api/pipelines/0",
    "/api/jobs/0/log",
]


@pytest.mark.parametrize("url", NOT_FOUND_URLS)
async def test_not_found(client, data, url: str) -> None:
    assert (await client.get(url)).status_code == 404


async def test_validates_window(client, data) -> None:
    assert (await client.get("/api/summary", params={"days": 0})).status_code == 422
    assert (await client.get("/api/summary", params={"scope": "nope"})).status_code == 422
