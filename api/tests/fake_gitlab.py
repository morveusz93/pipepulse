"""Stateful in-memory GitLab API for tests, plugged in through httpx.MockTransport."""

import re
from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import unquote

import httpx

from pipepulse.gitlab import GitLabClient

PROJECT_ID = 42
BASE = f"/api/v4/projects/{PROJECT_ID}"
# The list endpoint returns no timings; those only come from the detail endpoint.
LIST_FIELDS = ("id", "status", "ref", "sha", "source", "web_url", "created_at", "updated_at")


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class FakeGitLab:
    def __init__(self) -> None:
        self.pipelines: dict[int, dict[str, Any]] = {}
        self.failed_jobs: dict[int, list[dict[str, Any]]] = {}
        self.traces: dict[int, str | None] = {}  # None => 401, like anonymous trace access
        self.commits: dict[str, str] = {}
        self.calls: Counter[str] = Counter()
        # int => that HTTP status instead of a body
        self.token_info: dict[str, Any] | int = {
            "name": "pipepulse",
            "scopes": ["read_api"],
            "active": True,
            "expires_at": None,
        }
        self.projects: dict[int, dict[str, Any]] = {
            PROJECT_ID: {
                "id": PROJECT_ID,
                "name": "p",
                "path_with_namespace": "g/p",
                "web_url": "https://gitlab.example.com/g/p",
                "default_branch": "main",
            }
        }
        self.tokens_seen: list[str | None] = []

    def add_pipeline(
        self,
        pipeline_id: int,
        status: str,
        updated_at: datetime,
        *,
        ref: str = "main",
        sha: str = "a" * 40,
        source: str = "push",
        duration: int | None = 120,
    ) -> None:
        self.pipelines[pipeline_id] = {
            "id": pipeline_id,
            "status": status,
            "ref": ref,
            "sha": sha,
            "source": source,
            "web_url": f"https://gitlab.example.com/g/p/-/pipelines/{pipeline_id}",
            "created_at": iso(updated_at),
            "updated_at": iso(updated_at),
            "duration": duration,
            "queued_duration": 2.6,
            "started_at": iso(updated_at),
            "finished_at": iso(updated_at),
        }
        self.commits.setdefault(sha, f"commit {sha[:8]}")

    def add_failed_job(self, pipeline_id: int, job_id: int, trace: str | None) -> None:
        self.failed_jobs.setdefault(pipeline_id, []).append(
            {
                "id": job_id,
                "name": f"job-{job_id}",
                "stage": "test",
                "status": "failed",
                "failure_reason": "script_failure",
                "duration": 30.4,
                "web_url": f"https://gitlab.example.com/g/p/-/jobs/{job_id}",
                "finished_at": self.pipelines[pipeline_id]["finished_at"],
            }
        )
        self.traces[job_id] = trace

    def client(
        self, base_url: str = "https://gitlab.example.com", token: str = "glpat-test"
    ) -> GitLabClient:
        return GitLabClient(
            base_url, token, backoff_base=0, transport=httpx.MockTransport(self.handle)
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.tokens_seen.append(request.headers.get("PRIVATE-TOKEN"))
        path = request.url.path
        if path == "/api/v4/personal_access_tokens/self":
            if isinstance(self.token_info, int):
                return httpx.Response(self.token_info)
            return httpx.Response(200, json=self.token_info)
        if path == "/api/v4/user":
            return httpx.Response(200, json={"id": 1, "username": "me"})
        if path == "/api/v4/projects":
            search = request.url.params.get("search", "")
            found = [p for p in self.projects.values() if search in p["path_with_namespace"]]
            return httpx.Response(200, json=found)
        raw_path = unquote(request.url.raw_path.decode().split("?")[0])
        if m := re.fullmatch(r"/api/v4/projects/([^/]+(?:/[^/]+)*)", raw_path):
            ref = m[1]
            for p in self.projects.values():
                if ref in (str(p["id"]), p["path_with_namespace"]):
                    return httpx.Response(200, json=p)
        if path == f"{BASE}/pipelines":
            self.calls["list"] += 1
            since = request.url.params.get("updated_after")
            items = [
                {k: p[k] for k in LIST_FIELDS}
                for p in sorted(self.pipelines.values(), key=lambda p: -p["id"])
                if since is None
                or datetime.fromisoformat(p["updated_at"]) >= datetime.fromisoformat(since)
            ]
            return httpx.Response(200, json=items, headers={"x-next-page": ""})
        if m := re.fullmatch(rf"{BASE}/pipelines/(\d+)/jobs", path):
            return httpx.Response(200, json=self.failed_jobs.get(int(m[1]), []))
        if m := re.fullmatch(rf"{BASE}/pipelines/(\d+)", path):
            self.calls["detail"] += 1
            return httpx.Response(200, json=self.pipelines[int(m[1])])
        if m := re.fullmatch(rf"{BASE}/repository/commits/(\w+)", path):
            self.calls["commit"] += 1
            return httpx.Response(
                200, json={"id": m[1], "short_id": m[1][:8], "title": self.commits[m[1]]}
            )
        if m := re.fullmatch(rf"{BASE}/jobs/(\d+)/trace", path):
            trace = self.traces[int(m[1])]
            return httpx.Response(401) if trace is None else httpx.Response(200, text=trace)
        return httpx.Response(404)
