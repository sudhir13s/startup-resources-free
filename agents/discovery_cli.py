"""CLI entry: weekly-discovery cron calls `python -m agents.discovery_cli`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.discovery import discover_all, write_summary  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agents.discovery_cli")
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=5,
        help="Max ranked candidates kept per category (default 5).",
    )
    parser.add_argument(
        "--categories",
        type=lambda s: [c.strip() for c in s.split(",") if c.strip()] or None,
        default=None,
        help="Comma-separated subset (default: all).",
    )
    args = parser.parse_args(argv)

    summary = asyncio.run(
        discover_all(
            categories=args.categories,
            max_per_category=args.max_per_category,
        )
    )
    path = write_summary(summary)
    print(f"discovery summary written -> {path}")
    print(
        f"candidates={len(summary.candidates)} queries={summary.queries_run} "
        f"aggregators={summary.aggregators_fetched} "
        f"chain_exhausted={summary.chain_exhausted}"
    )
    # Non-zero exit when chain exhausted AND no aggregator hits — useful
    # signal in workflow logs but does NOT fail the cron.
    return 0


if __name__ == "__main__":
    sys.exit(main())
