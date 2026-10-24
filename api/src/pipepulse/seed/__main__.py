"""Seed demo data: `python -m pipepulse.seed [--if-demo-mode] [--days N]`."""

import argparse
import asyncio
import sys

from pipepulse.config import get_settings
from pipepulse.db import get_engine, get_sessionmaker
from pipepulse.seed.generator import seed_demo


async def run(days: int) -> None:
    settings = get_settings()
    async with get_sessionmaker()() as session:
        result = await seed_demo(session, days=days, trace_tail_lines=settings.trace_tail_lines)
        await session.commit()
    await get_engine().dispose()
    print(
        f"Seeded {result.projects} demo projects, {result.pipelines} pipelines, "
        f"{result.failed_jobs} failed jobs ({days} days of history)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace demo projects with generated history.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument(
        "--if-demo-mode",
        action="store_true",
        help="do nothing unless PIPEPULSE_DEMO_MODE is true (for container entrypoints)",
    )
    args = parser.parse_args()
    if args.if_demo_mode and not get_settings().demo_mode:
        print("Demo mode is off, skipping seed")
        sys.exit(0)
    asyncio.run(run(args.days))


if __name__ == "__main__":
    main()
