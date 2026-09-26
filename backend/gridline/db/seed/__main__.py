"""CLI: ``python -m gridline.db.seed [--reset] [--database-url URL] [--data-dir PATH]``."""

import argparse
import asyncio
import sys
from pathlib import Path

from gridline.config import BACKEND_DIR, Settings
from gridline.db.engine import create_engine, session_factory
from gridline.db.schema import create_schema
from gridline.db.seed.seed import SeedSummary, is_seeded, reset_and_seed, seed


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m gridline.db.seed", description=__doc__)
    parser.add_argument("--reset", action="store_true", help="drop and recreate every table before seeding")
    parser.add_argument("--database-url", default=None, help="SQLAlchemy URL (default: DATABASE_URL)")
    parser.add_argument(
        "--data-dir", type=Path, default=BACKEND_DIR / "data", help="directory with city/, corpus/"
    )
    return parser.parse_args(argv)


async def _run(url: str, data_dir: Path, reset: bool) -> SeedSummary | None:
    engine = create_engine(url)
    try:
        if reset:
            return await reset_and_seed(engine, data_dir)
        await create_schema(engine)
        if await is_seeded(engine):
            return None
        async with session_factory(engine)() as session, session.begin():
            return await seed(session, data_dir)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    url: str = args.database_url or Settings().database_url
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None  # psycopg async on Windows
    try:
        summary = asyncio.run(_run(url, args.data_dir, args.reset), loop_factory=loop_factory)
    except ValueError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    if summary is None:
        print("database already seeded; nothing written (pass --reset to drop and reseed)")
        return 0
    for name, count in summary.counts.items():
        print(f"{name:<28} {count:>6}")
    print(f"{'total':<28} {sum(summary.counts.values()):>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
