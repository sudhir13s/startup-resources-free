"""CLI entry: weekly-refresh cron calls `python -m agents.refresh_cli`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.refresh import refresh_all, write_summary  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agents.refresh_cli")
    parser.add_argument(
        "--rate-limit-s",
        type=float,
        default=30.0,
        help="Seconds between requests per host (default 30).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Cap rows processed (debug mode).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite DB (default: $RESOURCEOS_DB_PATH or data/resourceos.db).",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db) if args.db else None
    summary = asyncio.run(
        refresh_all(
            db_path=db_path,
            rate_limit_s=args.rate_limit_s,
            max_records=args.max_records,
        )
    )
    path = write_summary(summary)
    print(f"refresh summary written -> {path}")
    print(
        f"walked={summary.walked} changed={summary.changed} "
        f"unchanged={summary.unchanged} extract_failed={summary.extract_failed} "
        f"fetch_failed={summary.fetch_failed} pages={summary.pages_fetched} "
        f"follow_hits={summary.follow_hits}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
