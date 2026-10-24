"""Export the demo as a static snapshot for the frontend-only public demo.

    python -m pipepulse.seed.snapshot ../web/src/demo/snapshot.json

Seeds the database, then records the responses of the real API endpoints the dashboard uses, so
the snapshot's numbers are exactly what the backend computes. The frontend shifts every
timestamp by "now - generated_at" when serving it, so the demo never looks stale.

Needs a reachable database (PIPEPULSE_DATABASE_URL); demo projects in it are replaced.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from pipepulse.config import get_settings
from pipepulse.db import get_engine, get_sessionmaker
from pipepulse.deps import get_now
from pipepulse.main import app
from pipepulse.seed.generator import seed_demo

WINDOWS = (7, 30, 90)
DASHBOARD_WINDOW = 7
PAGE = 200  # API max page size


async def build_snapshot(days: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with get_sessionmaker()() as session:
        await seed_demo(
            session, now=now, days=days, trace_tail_lines=get_settings().trace_tail_lines
        )
        await session.commit()

    app.dependency_overrides[get_now] = lambda: now
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://snapshot") as client:

        async def get(path: str, **params: Any) -> Any:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

        projects = await get("/api/projects", days=DASHBOARD_WINDOW)
        snapshot: dict[str, Any] = {
            "generated_at": now.isoformat(),
            "summary": await get("/api/summary", days=DASHBOARD_WINDOW),
            "projects": {},
            "pipelines": [],
            "logs": {},
        }
        for project in projects:
            pid = project["id"]
            snapshot["projects"][pid] = {
                "rows": {w: await get(f"/api/projects/{pid}", days=w) for w in WINDOWS},
                "stats": {w: await get(f"/api/projects/{pid}/stats", days=w) for w in WINDOWS},
                "trend": {w: await get(f"/api/projects/{pid}/trend", days=w) for w in WINDOWS},
            }
            offset = 0
            while True:
                page = await get("/api/pipelines", project_id=pid, limit=PAGE, offset=offset)
                snapshot["pipelines"].extend(page["items"])
                offset += PAGE
                if offset >= page["total"]:
                    break

        for pipeline in snapshot["pipelines"]:
            for job in pipeline["failed_jobs"]:
                if job["has_log"]:
                    snapshot["logs"][job["id"]] = (await get(f"/api/jobs/{job['id']}/log"))["log"]
    app.dependency_overrides.clear()
    await get_engine().dispose()
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    snapshot = asyncio.run(build_snapshot(args.days))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, separators=(",", ":")))
    size_kb = args.out.stat().st_size / 1024
    print(
        f"Wrote {args.out} ({size_kb:.0f} KB): {len(snapshot['projects'])} projects, "
        f"{len(snapshot['pipelines'])} pipelines, {len(snapshot['logs'])} logs"
    )


if __name__ == "__main__":
    main()
