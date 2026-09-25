"""CLI entry for manual refresh runs: `python -m refresh run [...]`.

Not used in production (the API drives `refresh.runner.create_runner`
in-process) — this is for local testing and one-off manual sweeps.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

from domain.runs import RefreshOptions, RunReport
from refresh.runner import create_runner
from refresh.search import chain_status
from storage.seed_import import import_seed
from storage.sqlite_repository import SqliteRepository

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m refresh")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the refresh pipeline once.")
    run_p.add_argument("--providers", help="Comma-separated provider_ids (default: all).")
    run_p.add_argument("--discover", action="store_true", help="Also run discovery.")
    run_p.add_argument("--force", action="store_true", help="Ignore the page-hash gate.")
    run_p.add_argument("--db", default="data/resourceos.db", help="SQLite DB path.")
    run_p.add_argument("--seed", default="data/providers_seed.json", help="Seed JSON path.")
    run_p.add_argument("--max-llm-calls", type=int, default=200)

    status_p = sub.add_parser("search-status", help="Show search-chain availability + quota.")
    status_p.add_argument("--db", default="data/resourceos.db", help="SQLite DB path.")
    return parser


async def _run_command(args: argparse.Namespace) -> None:
    repo = SqliteRepository(args.db)
    try:
        import_seed(repo, args.seed)
        provider_ids = args.providers.split(",") if args.providers else None
        options = RefreshOptions(
            provider_ids=provider_ids,
            discover=args.discover,
            force=args.force,
            max_llm_calls=args.max_llm_calls,
        )
        report = RunReport(run_id=str(uuid.uuid4()), trigger="cli", options=options)
        repo.create_run(report)
        runner = create_runner(repo)
        finished = await runner.run(report)
        _print_report(finished)
    finally:
        repo.close()


def _print_report(report: RunReport) -> None:
    print(f"run_id={report.run_id} status={report.status}")
    print(f"llm_calls={report.llm_calls} search_calls={report.search_calls} "
          f"candidates_found={report.candidates_found}")
    print(f"{'provider_id':<30} {'status':<14} {'changes':<8} message")
    for outcome in report.outcomes:
        print(f"{outcome.provider_id:<30} {outcome.status:<14} {outcome.changes:<8} {outcome.message}")
    if report.errors:
        print("\nerrors:")
        for err in report.errors:
            print(f"  - {err}")
    counts = report.counts()
    print(f"\ntotals: {counts}")


def _search_status_command(args: argparse.Namespace) -> None:
    repo = SqliteRepository(args.db)
    try:
        status = chain_status(repo)
        print(f"providers_active: {status['providers_active']}")
        print(f"remaining: {status['remaining']}")
    finally:
        repo.close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        asyncio.run(_run_command(args))
        return 0
    if args.command == "search-status":
        _search_status_command(args)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
