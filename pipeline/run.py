"""Pipeline entry — runs all registered collectors politely.

Usage:
    python -m pipeline                     # run all collectors
    python -m pipeline --providers groq    # subset
    python -m pipeline --dry-run           # show plan, no fetch

What it does (v0.2 with-LLM-keys path is documented but stubbed here):
  1. for each Collector in collectors.REGISTRY:
     - check robots.txt
     - polite-fetch source_url (1 req / 30s / host)
     - save raw body to data/raw/<provider>/<date>.html
     - call collector.extract_fields() for a heuristic record
  2. compose the new snapshot from extracted records + the existing
     seed.json baseline (fields the heuristic couldn't parse stay
     from the previous snapshot).
  3. write data/snapshots/<today>.json (atomic).
  4. print a JSONL run summary to stdout.

The LLM extractor (v0.2 with keys) replaces step 1's heuristic
extract_fields with a `freellm.call_text(...)` call against the saved
raw HTML — see `.claude/rules/project/agentic-pipeline.md`. This file
ships the polite-fetch + heuristic-write loop only; the LLM step
is not invoked here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from collectors import REGISTRY, BaseCollector, FetchResult, PoliteClient  # noqa: E402

import snapshots as snap_module  # noqa: E402


SEED_PATH = REPO_ROOT / "data" / "seed.json"


def _load_seed_index() -> dict[str, dict[str, Any]]:
    if not SEED_PATH.exists():
        return {}
    with SEED_PATH.open(encoding="utf-8") as f:
        rows = json.load(f)
    return {r["id"]: r for r in rows}


def _merge_with_seed(
    extracted: dict[str, Any],
    seed: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fill blanks in `extracted` from `seed` so we don't lose fields
    the heuristic couldn't parse. The LLM extractor (v0.2) replaces
    this fallback with full extraction.
    """
    if seed is None:
        return extracted
    out = dict(seed)
    for k, v in extracted.items():
        if v not in (None, ""):
            out[k] = v
    return out


async def _run_one(
    collector: BaseCollector, client: PoliteClient
) -> tuple[FetchResult, dict[str, Any] | None]:
    fr = await collector.collect(client)
    record: dict[str, Any] | None = None
    if fr.is_ok and fr.text:
        record = collector.extract_fields(fr.text)
    return fr, record


async def _run(
    *,
    only: list[str] | None = None,
    dry_run: bool = False,
    rate_limit_s: float | None = None,
) -> int:
    chosen: list[BaseCollector] = REGISTRY.all()
    if only:
        only_set = set(only)
        chosen = [c for c in chosen if c.provider_id in only_set]
    if not chosen:
        print(json.dumps({"error": "no collectors matched", "filter": only}))
        return 2

    if dry_run:
        out = {
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
        print(json.dumps(out, indent=2))
        return 0

    summary: list[dict[str, Any]] = []
    seed_idx = _load_seed_index()
    extracted_by_id: dict[str, dict[str, Any]] = {}

    kwargs: dict[str, Any] = {}
    if rate_limit_s is not None:
        kwargs["rate_limit_s"] = rate_limit_s
    async with PoliteClient(**kwargs) as client:
        for c in chosen:
            try:
                fr, record = await _run_one(c, client)
            except Exception as e:  # noqa: BLE001 - top-level loop must not crash
                summary.append(
                    {
                        "provider_id": c.provider_id,
                        "status": "error",
                        "detail": str(e),
                    }
                )
                continue
            entry = {
                "provider_id": c.provider_id,
                "status_code": fr.status_code,
                "not_modified": fr.not_modified,
                "raw_path": str(fr.raw_path) if fr.raw_path else None,
                "extracted_confidence": (record or {}).get("parse_confidence"),
            }
            summary.append(entry)
            if record is not None:
                merged = _merge_with_seed(record, seed_idx.get(c.provider_id))
                extracted_by_id[c.provider_id] = merged

    # Compose new snapshot: start from the seed, override with anything
    # we successfully re-extracted.
    composed: dict[str, dict[str, Any]] = dict(seed_idx)
    composed.update(extracted_by_id)
    rows = list(composed.values())
    snap_path = snap_module.write_snapshot(rows)
    summary.append({"snapshot_written": str(snap_path), "records": len(rows)})
    print(json.dumps({"summary": summary}, indent=2))
    return 0


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
        "--rate-limit-s",
        type=float,
        default=None,
        help="Seconds between requests per host (default: 30)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(
        _run(only=args.providers, dry_run=args.dry_run, rate_limit_s=args.rate_limit_s)
    )


if __name__ == "__main__":
    sys.exit(main())
