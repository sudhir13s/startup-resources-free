"""Pipeline CLI entry point.

Usage:
    python -m pipeline                              # all collectors, mode=auto
    python -m pipeline --providers groq             # subset
    python -m pipeline --dry-run                    # show plan, no fetch
    python -m pipeline --mode heuristic             # no LLM
    python -m pipeline --mode llm                   # LLM-only (fail loud if no keys)
    python -m pipeline --no-db                      # skip SQLite write
    python -m pipeline --db /tmp/x.db               # custom DB path

Outputs JSON to stdout. Lock files at `data/runs/<run-id>.lock` prevent
double-runs (cron + manual concurrency).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collectors import REGISTRY  # noqa: E402
from pipeline.orchestrator import (  # noqa: E402
    acquire_lock,
    release_lock,
    run_pipeline,
)


def _dry_run_plan(only: list[str] | None) -> dict:
    chosen = REGISTRY.all()
    if only:
        only_set = set(only)
        chosen = [c for c in chosen if c.provider_id in only_set]
    return {
        "dry_run": True,
        "would_fetch": [
            {
                "provider_id": c.provider_id,
                "category": c.category,
                "source_url": c.source_url,
            }
            for c in chosen
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.run")
    parser.add_argument(
        "--providers",
        type=lambda s: [p.strip() for p in s.split(",") if p.strip()],
        default=None,
        help="Comma-separated provider ids (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("auto", "llm", "heuristic"),
        default="auto",
    )
    parser.add_argument(
        "--rate-limit-s",
        type=float,
        default=None,
        help="Seconds between requests per host (default: 30)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite DB (default: $RESOURCEOS_DB_PATH or data/resourceos.db)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip SQLite writes (useful in dry-runs / smoke tests).",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip writing data/snapshots/<date>.json (legacy FE shape).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="default",
        help="Lock-file id, default 'default'. Use unique values for parallel runs.",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        plan = _dry_run_plan(args.providers)
        if not plan["would_fetch"]:
            print(
                json.dumps(
                    {"error": "no collectors matched", "filter": args.providers}
                )
            )
            return 2
        print(json.dumps(plan, indent=2))
        return 0

    db_path: Path | None
    if args.no_db:
        db_path = None
    elif args.db:
        db_path = Path(args.db)
    else:
        from backend import db as db_module

        db_path = db_module.db_path()

    lock = acquire_lock(args.run_id)
    if lock is None:
        print(json.dumps({"error": "another run is in progress", "run_id": args.run_id}))
        return 3
    try:
        summary = asyncio.run(
            run_pipeline(
                only=args.providers,
                mode=args.mode,  # type: ignore[arg-type]
                rate_limit_s=args.rate_limit_s,
                db_path=db_path,
                write_snapshot=not args.no_snapshot,
            )
        )
    finally:
        release_lock(lock)

    print(json.dumps(summary.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Backward-compat shim — older tests imported `_run`. Delegates to the new
# orchestrator with mode='heuristic' (no LLM keys assumed in those tests).
async def _run(
    *,
    only: list[str] | None = None,
    dry_run: bool = False,
    rate_limit_s: float | None = None,
) -> int:
    if dry_run:
        print(json.dumps(_dry_run_plan(only), indent=2))
        return 0
    summary = await run_pipeline(
        only=only,
        mode="heuristic",
        rate_limit_s=rate_limit_s,
        db_path=None,
    )
    print(json.dumps(summary.to_dict(), indent=2))
    return 0
