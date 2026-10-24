from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from pipepulse.gitlab import GitLabAuthError, GitLabClient, GitLabError, GitLabNotFoundError

Handler = Callable[[httpx.Request], httpx.Response]

PIPELINE = {
    "id": 101,
    "status": "failed",
    "ref": "main",
    "sha": "a" * 40,
    "source": "push",
    "web_url": "https://gitlab.example.com/g/p/-/pipelines/101",
    "created_at": "2026-10-24T10:00:00.000Z",
    "updated_at": "2026-10-24T10:05:00.000Z",
}


def make_client(handler: Handler, token: str | None = "glpat-secret") -> GitLabClient:
    return GitLabClient(
        "https://gitlab.example.com/",
        token,
        backoff_base=0,
        transport=httpx.MockTransport(handler),
    )


async def test_sends_token_and_encodes_project_path() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": 7,
                "name": "api",
                "path_with_namespace": "group/sub/api",
                "web_url": "https://gitlab.example.com/group/sub/api",
                "default_branch": "main",
                "unknown_field": "ignored",
            },
        )

    async with make_client(handler) as client:
        project = await client.get_project("group/sub/api")

    assert project.id == 7
    assert seen[0].url.raw_path == b"/api/v4/projects/group%2Fsub%2Fapi"
    assert seen[0].headers["PRIVATE-TOKEN"] == "glpat-secret"


async def test_omits_token_header_when_anonymous() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "PRIVATE-TOKEN" not in request.headers
        return httpx.Response(200, json=[])

    async with make_client(handler, token=None) as client:
        assert [p async for p in client.iter_pipelines(1)] == []


async def test_iter_pipelines_follows_pagination_and_passes_filters() -> None:
    pages = {
        "1": ([PIPELINE], "2"),
        "2": ([{**PIPELINE, "id": 100, "status": "success"}], ""),
    }
    seen_params: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.append(request.url.params)
        items, next_page = pages[request.url.params["page"]]
        return httpx.Response(200, json=items, headers={"x-next-page": next_page})

    since = datetime(2026, 10, 1, tzinfo=UTC)
    async with make_client(handler) as client:
        pipelines = [p async for p in client.iter_pipelines(1, updated_after=since)]

    assert [p.id for p in pipelines] == [101, 100]
    assert pipelines[0].created_at == datetime(2026, 10, 24, 10, 0, tzinfo=UTC)
    assert seen_params[0]["updated_after"] == "2026-10-01T00:00:00+00:00"
    assert seen_params[0]["order_by"] == "id"


async def test_get_pipeline_parses_timings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                **PIPELINE,
                "duration": 252,
                "queued_duration": 3.4,
                "started_at": "2026-10-24T10:00:03.000Z",
                "finished_at": "2026-10-24T10:04:15.000Z",
            },
        )

    async with make_client(handler) as client:
        pipeline = await client.get_pipeline(1, 101)

    assert pipeline.duration == 252
    assert pipeline.finished_at == datetime(2026, 10, 24, 10, 4, 15, tzinfo=UTC)


async def test_list_pipeline_jobs_requests_failed_scope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("scope[]") == ["failed"]
        job = {
            "id": 9,
            "name": "test:e2e",
            "stage": "test",
            "status": "failed",
            "failure_reason": "script_failure",
            "duration": 61.2,
            "web_url": "https://gitlab.example.com/g/p/-/jobs/9",
            "finished_at": "2026-10-24T10:04:00.000Z",
        }
        return httpx.Response(200, json=[job])

    async with make_client(handler) as client:
        jobs = await client.list_pipeline_jobs(1, 101)

    assert [(j.name, j.failure_reason) for j in jobs] == [("test:e2e", "script_failure")]


async def test_trace_tail_keeps_last_lines_across_chunk_boundaries() -> None:
    log = "".join(f"line {i}\n" for i in range(1, 1001)) + "\x1b[31mERROR: boom\x1b[0m"

    async def chunks():
        # Odd chunk size so lines get split mid-way.
        for i in range(0, len(log), 7):
            yield log[i : i + 7].encode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v4/projects/1/jobs/9/trace"
        return httpx.Response(200, content=chunks())

    async with make_client(handler) as client:
        tail = await client.get_job_trace_tail(1, 9, lines=3)

    assert tail == "line 999\nline 1000\n\x1b[31mERROR: boom\x1b[0m"


async def test_retries_rate_limit_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"id": "a" * 40, "short_id": "aaaaaaaa", "title": "fix"})

    async with make_client(handler) as client:
        commit = await client.get_commit(1, "a" * 40)

    assert commit.title == "fix"
    assert calls == 3


async def test_gives_up_after_max_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with make_client(handler) as client:
        with pytest.raises(GitLabError) as exc_info:
            await client.get_project(1)

    assert exc_info.value.status_code == 503


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, GitLabAuthError), (403, GitLabAuthError), (404, GitLabNotFoundError)],
)
async def test_maps_error_statuses(status: int, error: type[GitLabError]) -> None:
    async with make_client(lambda request: httpx.Response(status)) as client:
        with pytest.raises(error):
            await client.get_project(1)


async def test_error_message_never_contains_token() -> None:
    async with make_client(lambda request: httpx.Response(401)) as client:
        with pytest.raises(GitLabAuthError) as exc_info:
            await client.get_project(1)

    assert "glpat-secret" not in str(exc_info.value)
