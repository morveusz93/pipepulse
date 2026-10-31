import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pipepulse.config import Settings
from pipepulse.models import Pipeline, Project
from pipepulse.sync import SyncOptions
from pipepulse.worker import check_token, poll_once, reconcile_projects
from tests.fake_gitlab import PROJECT_ID, FakeGitLab

OPTIONS = SyncOptions(backfill_days=30)


def tracked_project(gitlab_id: int, path: str, *, demo: bool = False) -> Project:
    return Project(
        gitlab_project_id=gitlab_id,
        is_demo=demo,
        path_with_namespace=path,
        name=path.rsplit("/", 1)[-1],
        web_url=f"https://gitlab.example.com/{path}",
        default_branch="main",
    )


async def give_history(session: AsyncSession, path: str) -> None:
    project = (await projects(session))[path]
    session.add(
        Pipeline(
            project_id=project.id,
            gitlab_pipeline_id=project.id,
            status="success",
            ref="main",
            sha="a" * 40,
            web_url="https://gitlab.example.com/p",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def projects(session: AsyncSession) -> dict[str, Project]:
    session.expire_all()
    return {p.path_with_namespace: p for p in await session.scalars(select(Project))}


async def reconcile(sessionmaker, gitlab: FakeGitLab, paths: list[str]) -> list[int]:
    async with gitlab.client() as client:
        return await reconcile_projects(sessionmaker, client, paths)


# --- configuration --------------------------------------------------------------------------


def test_project_paths_parsing() -> None:
    settings = Settings(projects=" group/api, group/web\ngroup/API  /group/infra/ ,, ")
    assert settings.project_paths == ["group/api", "group/web", "group/infra"]
    assert Settings(projects="").project_paths == []


# --- reconcile ------------------------------------------------------------------------------


async def test_adds_configured_projects_from_gitlab(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_project(7, "group/web", default_branch="develop")

    ids = await reconcile(sessionmaker, gitlab, ["g/p", "group/web"])

    stored = await projects(session)
    assert [stored["g/p"].id, stored["group/web"].id] == ids
    assert stored["group/web"].gitlab_project_id == 7
    assert stored["group/web"].default_branch == "develop"
    assert stored["g/p"].is_demo is False


async def test_unknown_project_is_skipped(
    sessionmaker: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="pipepulse.worker"):
        ids = await reconcile(sessionmaker, FakeGitLab(), ["nope/missing", "g/p"])

    assert len(ids) == 1
    assert set(await projects(session)) == {"g/p"}
    assert "nope/missing: project not found" in caplog.text


async def test_known_paths_need_no_gitlab_lookup(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    session.add(tracked_project(PROJECT_ID, "g/p"))
    await session.commit()
    gitlab = FakeGitLab()

    await reconcile(sessionmaker, gitlab, ["G/P"])

    assert gitlab.tokens_seen == []  # matched case-insensitively, no request made


async def test_unlisted_projects_are_marked_removed_keeping_history(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    old = tracked_project(99, "group/old")
    old.pipelines.append(
        Pipeline(
            gitlab_pipeline_id=1,
            status="success",
            ref="main",
            sha="a" * 40,
            web_url="https://gitlab.example.com/p",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    session.add_all([old, tracked_project(1001, "acme/demo", demo=True)])
    await session.commit()

    ids = await reconcile(sessionmaker, FakeGitLab(), ["g/p"])

    stored = await projects(session)
    assert stored["group/old"].removed_at is not None
    assert stored["group/old"].id not in ids  # no longer polled
    assert stored["acme/demo"].removed_at is None
    assert stored["g/p"].removed_at is None
    assert await session.scalar(select(func.count()).select_from(Pipeline)) == 1


async def test_reconfigured_project_is_restored(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    await reconcile(sessionmaker, FakeGitLab(), ["g/p"])
    await give_history(session, "g/p")
    gitlab = FakeGitLab()
    gitlab.add_project(7, "group/web")
    await reconcile(sessionmaker, gitlab, ["group/web"])
    assert (await projects(session))["g/p"].removed_at is not None

    ids = await reconcile(sessionmaker, gitlab, ["g/p", "group/web"])

    stored = await projects(session)
    assert stored["g/p"].removed_at is None
    assert stored["g/p"].id in ids


async def test_finding_nothing_marks_nothing(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    session.add(tracked_project(99, "group/old"))
    await session.commit()

    assert await reconcile(sessionmaker, FakeGitLab(), ["typo/nope"]) == []
    assert (await projects(session))["group/old"].removed_at is None


async def test_empty_list_tracks_every_accessible_project_with_ci(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_project(7, "group/web")
    gitlab.add_project(8, "group/docs", ci=False)

    ids = await reconcile(sessionmaker, gitlab, [])

    stored = await projects(session)
    assert set(stored) == {"g/p", "group/web"}
    assert sorted(ids) == sorted(p.id for p in stored.values())

    # Losing access to a project with history marks it removed on the next cycle.
    await give_history(session, "group/web")
    del gitlab.projects[7]
    ids = await reconcile(sessionmaker, gitlab, [])
    assert (await projects(session))["group/web"].removed_at is not None
    assert len(ids) == 1


async def test_dropped_project_without_history_is_deleted_outright(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    session.add(tracked_project(99, "group/never-ran-ci"))
    await session.commit()

    await reconcile(sessionmaker, FakeGitLab(), ["g/p"])

    assert set(await projects(session)) == {"g/p"}


async def test_renamed_project_keeps_its_history(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    project = tracked_project(PROJECT_ID, "old-group/p")
    session.add(project)
    await session.commit()
    original_id = project.id

    # Config now uses the new path, which GitLab resolves to the same project id.
    ids = await reconcile(sessionmaker, FakeGitLab(), ["g/p"])

    stored = await projects(session)
    assert ids == [original_id]
    assert set(stored) == {"g/p"}


# --- polling --------------------------------------------------------------------------------


async def test_poll_once_tracks_and_syncs(
    sessionmaker: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    gitlab = FakeGitLab()
    gitlab.add_pipeline(1, "success", datetime.now(UTC) - timedelta(hours=1))
    gitlab.add_pipeline(2, "failed", datetime.now(UTC) - timedelta(minutes=5))
    gitlab.add_failed_job(2, 201, trace="boom")

    async with gitlab.client() as client:
        await poll_once(sessionmaker, client, ["g/p"], OPTIONS)

    stored = (await projects(session))["g/p"]
    assert stored.last_polled_at is not None
    assert await session.scalar(select(func.count()).select_from(Pipeline)) == 2


async def test_poll_stops_when_the_token_is_rejected(
    sessionmaker: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session.add_all([tracked_project(PROJECT_ID, "g/p"), tracked_project(7, "group/web")])
    await session.commit()
    gitlab = FakeGitLab()
    gitlab.handle = lambda request: httpx.Response(401)  # type: ignore[method-assign]

    with caplog.at_level(logging.ERROR, logger="pipepulse.worker"):
        async with gitlab.client() as client:
            await poll_once(sessionmaker, client, ["g/p", "group/web"], OPTIONS)

    assert caplog.text.count("token rejected") == 1  # the second project isn't attempted


async def test_rejected_token_during_lookup_is_logged_cleanly(
    sessionmaker: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    gitlab = FakeGitLab()
    gitlab.handle = lambda request: httpx.Response(401)  # type: ignore[method-assign]

    with caplog.at_level(logging.ERROR, logger="pipepulse.worker"):
        async with gitlab.client() as client:
            await poll_once(sessionmaker, client, ["g/p"], OPTIONS)

    [record] = caplog.records
    assert "rejected the token while looking up projects" in record.getMessage()
    assert record.exc_info is None


# --- token check ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token_info", "level", "message"),
    [
        (
            {"name": "t", "scopes": ["read_user"], "active": True},
            logging.ERROR,
            "lacks the read_api",
        ),
        ({"name": "t", "scopes": ["api"], "active": True}, logging.WARNING, "full api scope"),
        (401, logging.ERROR, "rejected PIPEPULSE_GITLAB_TOKEN"),
        (404, logging.INFO, "Could not inspect the token"),
    ],
)
async def test_check_token_logs_problems(
    caplog: pytest.LogCaptureFixture, token_info: dict | int, level: int, message: str
) -> None:
    gitlab = FakeGitLab()
    gitlab.token_info = token_info

    with caplog.at_level(logging.INFO, logger="pipepulse.worker"):
        async with gitlab.client() as client:
            await check_token(client)

    [record] = [r for r in caplog.records if message in r.getMessage()]
    assert record.levelno == level
