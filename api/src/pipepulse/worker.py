"""Background poller: `python -m pipepulse.worker`.

Runs as its own process (own container / k8s Deployment with one replica), so scaling the
API never multiplies GitLab polling. What to poll comes from configuration
(PIPEPULSE_GITLAB_URL, PIPEPULSE_GITLAB_TOKEN and optionally PIPEPULSE_PROJECTS).
"""

import asyncio
import contextlib
import logging
import signal
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pipepulse.config import Settings, get_settings
from pipepulse.db import get_sessionmaker
from pipepulse.gitlab import GitLabAuthError, GitLabClient, GitLabError, GitLabNotFoundError
from pipepulse.gitlab.schemas import GitLabProject
from pipepulse.models import Pipeline, Project
from pipepulse.sync import SyncOptions, sync_project

logger = logging.getLogger("pipepulse.worker")

READ_SCOPES = {"read_api", "api"}


async def reconcile_projects(
    sessionmaker: async_sessionmaker[AsyncSession], client: GitLabClient, paths: list[str]
) -> list[int]:
    """Make the tracked (non-demo) projects match the configuration; returns the ids to poll.

    With `paths`, those projects are tracked (looked up in GitLab only when not known yet).
    Without, every project the token can see pipelines of is. Projects that drop out are
    marked removed (not polled, history kept) and restored if they come back; deleting their
    history is left to the user, from the dashboard.
    """
    async with sessionmaker() as session:
        tracked = list(await session.scalars(select(Project).where(Project.is_demo.is_(False))))
        by_path = {p.path_with_namespace.lower(): p for p in tracked}
        by_gitlab_id = {p.gitlab_project_id: p for p in tracked}

        def upsert(found: GitLabProject) -> Project:
            # Matching on GitLab's id keeps the history of renamed projects.
            project = by_gitlab_id.get(found.id)
            if project is None:
                project = Project(gitlab_project_id=found.id)
                session.add(project)
                by_gitlab_id[found.id] = project
                logger.info("%s: now tracked, backfilling history", found.path_with_namespace)
            project.path_with_namespace = found.path_with_namespace
            project.name = found.name
            project.web_url = found.web_url
            project.default_branch = found.default_branch
            return project

        wanted: list[Project] = []
        if paths:
            for path in paths:
                project = by_path.get(path.lower())
                if project is None:
                    try:
                        project = upsert(await client.get_project(path))
                    except GitLabNotFoundError:
                        logger.error("%s: project not found, or the token can't access it", path)
                        continue
                wanted.append(project)
        else:
            async for found in client.iter_accessible_projects():
                if found.jobs_enabled is not False:
                    wanted.append(upsert(found))

        now = datetime.now(UTC)
        keep = {id(p) for p in wanted}
        for project in wanted:
            if project.removed_at is not None:
                logger.info("%s is configured again, resuming", project.path_with_namespace)
                project.removed_at = None
        # Finding nothing at all (a typo, a token that lost access) must not flag every project.
        if wanted:
            dropped = [p for p in tracked if id(p) not in keep and p.removed_at is None]
            with_history = set(
                await session.scalars(
                    select(Pipeline.project_id)
                    .where(Pipeline.project_id.in_([p.id for p in dropped]))
                    .distinct()
                )
            )
            for project in dropped:
                if project.id not in with_history:
                    # Nothing to keep, so nothing for the user to confirm.
                    logger.info("%s is no longer configured, removed", project.path_with_namespace)
                    await session.delete(project)
                    continue
                logger.warning(
                    "%s is no longer configured: stopped polling, history kept until "
                    "deleted from the dashboard",
                    project.path_with_namespace,
                )
                project.removed_at = now
        await session.commit()
        return [p.id for p in wanted]


async def poll_once(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: GitLabClient,
    paths: list[str],
    options: SyncOptions,
) -> None:
    try:
        project_ids = await reconcile_projects(sessionmaker, client, paths)
    except GitLabAuthError as exc:
        logger.error("GitLab rejected the token while looking up projects (%s)", exc)
        return
    except GitLabError as exc:
        logger.warning("Could not look up configured projects: %s", exc)
        return
    for project_id in project_ids:
        if not await _poll_project(sessionmaker, client, project_id, options):
            return  # the token was rejected; every other project would fail the same way


async def _poll_project(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: GitLabClient,
    project_id: int,
    options: SyncOptions,
) -> bool:
    """Sync one project in its own transaction. Returns False if the token was rejected."""
    async with sessionmaker() as session:
        project = await session.get(Project, project_id)
        if project is None:  # deleted meanwhile
            return True
        try:
            result = await sync_project(session, client, project, options)
            await session.commit()
        except GitLabAuthError as exc:
            logger.error("%s: token rejected (%s)", project.path_with_namespace, exc)
            return False
        except GitLabError as exc:
            logger.warning("%s: sync failed: %s", project.path_with_namespace, exc)
            return True
        logger.info("%s: %s", project.path_with_namespace, result)
        return True


async def check_token(client: GitLabClient) -> None:
    """Log what's wrong with the token up front instead of failing quietly on every poll."""
    try:
        info = await client.get_token_info()
    except GitLabAuthError:
        logger.error("GitLab rejected PIPEPULSE_GITLAB_TOKEN (invalid, expired or revoked)")
        return
    except GitLabError as exc:
        # Older GitLab (< 15.5) can't describe its tokens; polling will show if it works.
        logger.info("Could not inspect the token (%s), continuing", exc)
        return
    if not READ_SCOPES & set(info.scopes):
        logger.error("Token %r lacks the read_api scope (has: %s)", info.name, info.scopes)
    elif "api" in info.scopes:
        logger.warning("Token %r has the full api scope; read_api is enough", info.name)
    if info.expires_at:
        logger.info("Token %r expires on %s", info.name, info.expires_at)


def sync_options(settings: Settings) -> SyncOptions:
    return SyncOptions(
        backfill_days=settings.backfill_days,
        trace_tail_lines=settings.trace_tail_lines,
        ignored_sources=frozenset(settings.ignored_sources),
    )


async def run_forever() -> None:
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    paths = settings.project_paths
    token = settings.gitlab_token.get_secret_value().strip() if settings.gitlab_token else ""
    if not token:
        # Demo deployments have no token; idle instead of crash-looping.
        logger.warning("PIPEPULSE_GITLAB_TOKEN is not set, nothing to poll. Idling.")
        await stop.wait()
        return

    options, sessionmaker = sync_options(settings), get_sessionmaker()
    async with GitLabClient(settings.gitlab_url, token) as client:
        await check_token(client)
        which = f"{len(paths)} configured project(s)" if paths else "all accessible projects"
        logger.info(
            "Polling %s on %s every %ss", which, settings.gitlab_url, settings.poll_interval_seconds
        )
        while not stop.is_set():
            try:
                await poll_once(sessionmaker, client, paths, options)
            except Exception:
                logger.exception("Poll cycle failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.poll_interval_seconds)
    logger.info("Worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # One line per HTTP request drowns the sync summaries; failures are logged by us anyway.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
