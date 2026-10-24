import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from typing import Any, Self
from urllib.parse import quote

import httpx

from pipepulse.gitlab.schemas import (
    GitLabCommit,
    GitLabJob,
    GitLabPipeline,
    GitLabPipelineDetail,
    GitLabProject,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
MAX_RETRY_AFTER_S = 60.0


class GitLabError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GitLabAuthError(GitLabError):
    """401/403: token invalid, expired, revoked or missing the read_api scope."""


class GitLabNotFoundError(GitLabError):
    """404: also what GitLab returns for projects the token cannot see."""


ProjectRef = int | str  # numeric id or "group/subgroup/project" path


def _project_path(project: ProjectRef) -> str:
    return f"/projects/{quote(str(project), safe='')}"


class GitLabClient:
    """Async read-only client for the GitLab REST API v4.

    The token is sent only in the PRIVATE-TOKEN header and never logged.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json", "User-Agent": "pipepulse"}
        if token:
            headers["PRIVATE-TOKEN"] = token
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v4",
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- public API -------------------------------------------------------------------------

    async def get_project(self, project: ProjectRef) -> GitLabProject:
        return GitLabProject.model_validate(await self._get_json(_project_path(project)))

    async def iter_pipelines(
        self,
        project: ProjectRef,
        *,
        updated_after: datetime | None = None,
        per_page: int = 100,
    ) -> AsyncIterator[GitLabPipeline]:
        """Newest first. Pass updated_after for incremental polling."""
        params: dict[str, Any] = {"order_by": "id", "sort": "desc", "per_page": per_page}
        if updated_after is not None:
            params["updated_after"] = updated_after.isoformat()
        async for item in self._paginate(f"{_project_path(project)}/pipelines", params):
            yield GitLabPipeline.model_validate(item)

    async def get_pipeline(self, project: ProjectRef, pipeline_id: int) -> GitLabPipelineDetail:
        data = await self._get_json(f"{_project_path(project)}/pipelines/{pipeline_id}")
        return GitLabPipelineDetail.model_validate(data)

    async def list_pipeline_jobs(
        self, project: ProjectRef, pipeline_id: int, *, scope: Iterable[str] = ("failed",)
    ) -> list[GitLabJob]:
        path = f"{_project_path(project)}/pipelines/{pipeline_id}/jobs"
        params = {"scope[]": list(scope), "per_page": 100}
        return [GitLabJob.model_validate(item) async for item in self._paginate(path, params)]

    async def get_commit(self, project: ProjectRef, sha: str) -> GitLabCommit:
        data = await self._get_json(f"{_project_path(project)}/repository/commits/{sha}")
        return GitLabCommit.model_validate(data)

    async def get_job_trace_tail(self, project: ProjectRef, job_id: int, lines: int = 50) -> str:
        """Last `lines` lines of a job log, streamed so large traces never sit in memory.

        Raw text is preserved (ANSI colors, GitLab section markers) for the log viewer.
        """
        tail: deque[str] = deque(maxlen=lines)
        pending = ""
        response = await self._send("GET", f"{_project_path(project)}/jobs/{job_id}/trace")
        try:
            async for chunk in response.aiter_text():
                *complete, pending = (pending + chunk).split("\n")
                tail.extend(complete)
        finally:
            await response.aclose()
        if pending:
            tail.append(pending)
        return "\n".join(tail)

    # --- transport --------------------------------------------------------------------------

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._send("GET", path, params)
        try:
            await response.aread()
            return response.json()
        finally:
            await response.aclose()

    async def _paginate(self, path: str, params: dict[str, Any]) -> AsyncIterator[Any]:
        page: str | None = "1"
        while page:
            response = await self._send("GET", path, {**params, "page": page})
            try:
                await response.aread()
                items = response.json()
                page = response.headers.get("x-next-page") or None
            finally:
                await response.aclose()
            for item in items:
                yield item

    async def _send(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Send with retries on rate limiting and gateway errors.

        Returns an open streaming response that the caller must close.
        """
        request = self._http.build_request(method, path, params=params)
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.send(request, stream=True)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise GitLabError(f"{method} {path}: {exc.__class__.__name__}") from exc
                await asyncio.sleep(self._backoff_base * 2**attempt)
                continue

            if response.status_code in RETRYABLE_STATUSES and attempt < self._max_retries:
                await response.aclose()
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "GitLab %s %s returned %s, retrying in %.1fs",
                    method,
                    path,
                    response.status_code,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if response.is_success:
                return response
            await response.aclose()
            raise self._error_for(method, path, response.status_code)

        raise AssertionError("unreachable")

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), MAX_RETRY_AFTER_S)
            except ValueError:
                pass
        return self._backoff_base * 2**attempt

    @staticmethod
    def _error_for(method: str, path: str, status_code: int) -> GitLabError:
        message = f"{method} {path} failed with HTTP {status_code}"
        if status_code in (401, 403):
            return GitLabAuthError(message, status_code)
        if status_code == 404:
            return GitLabNotFoundError(message, status_code)
        return GitLabError(message, status_code)
