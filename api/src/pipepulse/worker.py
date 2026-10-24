"""Background poller: `python -m pipepulse.worker`.

Runs as its own process (own container / k8s Deployment with one replica), so scaling the
API never multiplies GitLab polling.
"""

import asyncio
import contextlib
import logging
import signal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from pipepulse.config import Settings, get_settings
from pipepulse.crypto import (
    EncryptionKeyMissingError,
    TokenCipher,
    TokenDecryptionError,
    get_cipher,
)
from pipepulse.db import get_sessionmaker
from pipepulse.gitlab import GitLabAuthError, GitLabClient, GitLabError
from pipepulse.models import Connection, Project
from pipepulse.sync import SyncOptions, sync_project

logger = logging.getLogger("pipepulse.worker")


async def poll_once(
    sessionmaker: async_sessionmaker[AsyncSession], cipher: TokenCipher, options: SyncOptions
) -> None:
    async with sessionmaker() as session:
        connections = (
            await session.scalars(select(Connection).options(selectinload(Connection.projects)))
        ).all()

    for connection in connections:
        try:
            token = cipher.decrypt(connection.token_encrypted)
        except TokenDecryptionError:
            logger.error("Connection %r: token cannot be decrypted, skipping", connection.name)
            continue

        async with GitLabClient(connection.base_url, token) as client:
            for project in connection.projects:
                if not await _poll_project(sessionmaker, client, project.id, options):
                    break  # auth failed — the rest of this connection would fail the same way


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

    try:
        cipher = get_cipher()
    except EncryptionKeyMissingError:
        # Demo deployments have no key and no connections — idle instead of crash-looping.
        logger.warning("No encryption key configured, nothing to poll. Idling.")
        await stop.wait()
        return
    options, sessionmaker = sync_options(settings), get_sessionmaker()

    logger.info("Polling every %ss", settings.poll_interval_seconds)
    while not stop.is_set():
        try:
            await poll_once(sessionmaker, cipher, options)
        except Exception:
            logger.exception("Poll cycle failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.poll_interval_seconds)
    logger.info("Worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
