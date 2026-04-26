"""Snapshots + change-detector — pure-code persistence layer.

Render free-tier Web Services have NO persistent disk, so SQLite-on-disk
gets wiped between restarts. Phase 2 persistence strategy: snapshots are
stored as committed JSON files under `data/snapshots/<YYYY-MM-DD>.json`.
The daily GH Actions cron (when LLM keys land) writes a new snapshot
each morning, commits to `main`, Render auto-redeploys with the fresh
file. Source of truth = git history. Append-only by construction.

This module:
- Lists snapshots in chronological order.
- Loads any snapshot by date.
- Computes field-level diffs between two snapshots.
- Surfaces a flat list of `Change` records for the Changes tab API.

NO LLM calls live here. The agentic pipeline (Phase 2c+) writes
new snapshots via `write_snapshot()`; this module ships v0.1 with
just the read + diff path so the Changes-tab UI can land before
the cron does.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

SNAPSHOT_DIR = Path(__file__).parent.parent / "data" / "snapshots"
SEED_PATH = Path(__file__).parent.parent / "data" / "seed.json"

# Filename: 2026-04-26.json
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


# === Types ===

ChangeSeverity = Literal["new", "improved", "reduced", "ended", "unchanged"]


class Change(BaseModel):
    """One field-level change between two snapshots, surfaced to /api/changes."""

    provider_id: str
    provider_name: str
    category: str
    field: str
    old_value: Any | None
    new_value: Any | None
    severity: ChangeSeverity
    snapshot_date: str  # ISO YYYY-MM-DD of the NEW snapshot
    detected_at: str  # ISO datetime when diff was computed


class ChangesResponse(BaseModel):
    total: int
    items: list[Change]
    snapshot_dates: list[str]  # all known snapshot dates, ascending
    latest_snapshot: str | None


# === I/O ===


def list_snapshots() -> list[str]:
    """Return all snapshot dates (YYYY-MM-DD) in ascending order."""
    if not SNAPSHOT_DIR.exists():
        return []
    dates: list[str] = []
    for p in SNAPSHOT_DIR.iterdir():
        m = _DATE_RE.match(p.name)
        if m:
            dates.append(m.group(1))
    return sorted(dates)


def load_snapshot(date_str: str) -> list[dict[str, Any]]:
    """Load the records from `data/snapshots/<date>.json`.

    Raises FileNotFoundError if no such snapshot exists.
    """
    path = SNAPSHOT_DIR / f"{date_str}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_snapshot(records: list[dict[str, Any]], snap_date: date | None = None) -> Path:
    """Atomically write `records` to `data/snapshots/<snap_date>.json`.

    Used by the v0.2 cron pipeline. Idempotent: same date overwrites
    same file. Writes via tmp + rename to avoid partial reads.
    """
    snap_date = snap_date or datetime.now(tz=timezone.utc).date()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{snap_date.isoformat()}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


# === Diff ===

# Fields whose change is meaningful for the Changes tab. Skip `scraped_at`,
# `last_verified_at`, `id` etc. (they change every run without signal).
SIGNIFICANT_FIELDS = (
    "headline",
    "free_tier_summary",
    "quota_summary",
    "duration_summary",
    "region_summary",
    "offer_type",
    "eligibility_summary",
    "use_case_tiers",
    "india_accessible",
    "geo_priority",
    "parse_confidence",
)


def _index_by_id(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in records if "id" in r}


def _is_quota_reduction(field: str, old: Any, new: Any) -> bool:
    """Heuristic: `quota_summary` etc. that mention a smaller number ⇒ reduced.
    Imperfect; the Changes-tab severity badge is a hint, not a contract.
    """
    if not isinstance(old, str) or not isinstance(new, str):
        return False
    nums_old = [float(n) for n in re.findall(r"[\d,]+\.?\d*", old.replace(",", ""))]
    nums_new = [float(n) for n in re.findall(r"[\d,]+\.?\d*", new.replace(",", ""))]
    if not nums_old or not nums_new:
        return False
    return max(nums_new) < max(nums_old)


def _classify(field: str, old: Any, new: Any) -> ChangeSeverity:
    if old is None and new is not None:
        return "new"
    if old is not None and new is None:
        return "ended"
    if old == new:
        return "unchanged"
    if _is_quota_reduction(field, old, new):
        return "reduced"
    if isinstance(old, str) and isinstance(new, str):
        nums_old = [float(n) for n in re.findall(r"[\d,]+\.?\d*", old.replace(",", ""))]
        nums_new = [float(n) for n in re.findall(r"[\d,]+\.?\d*", new.replace(",", ""))]
        if nums_old and nums_new and max(nums_new) > max(nums_old):
            return "improved"
    # Default for non-numeric textual / list / bool changes.
    return "improved" if (new is not None and (old is None or old == "" or old is False)) else "reduced"


def diff_snapshots(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    *,
    snap_date: str,
) -> list[Change]:
    """Return field-level changes between `old` and `new` snapshots.

    Skips fields not in SIGNIFICANT_FIELDS (noise reduction).
    Records appearing only in `new` -> `severity="new"` per significant field.
    Records appearing only in `old` -> `severity="ended"` per significant field.
    """
    old_idx = _index_by_id(old)
    new_idx = _index_by_id(new)
    detected_at = datetime.now(tz=timezone.utc).isoformat()
    changes: list[Change] = []

    all_ids = set(old_idx) | set(new_idx)
    for pid in sorted(all_ids):
        old_rec = old_idx.get(pid)
        new_rec = new_idx.get(pid)
        # Provider added entirely.
        if old_rec is None and new_rec is not None:
            changes.append(
                Change(
                    provider_id=pid,
                    provider_name=new_rec.get("name", pid),
                    category=new_rec.get("category", ""),
                    field="__provider__",
                    old_value=None,
                    new_value=new_rec.get("headline", ""),
                    severity="new",
                    snapshot_date=snap_date,
                    detected_at=detected_at,
                )
            )
            continue
        # Provider removed entirely.
        if new_rec is None and old_rec is not None:
            changes.append(
                Change(
                    provider_id=pid,
                    provider_name=old_rec.get("name", pid),
                    category=old_rec.get("category", ""),
                    field="__provider__",
                    old_value=old_rec.get("headline", ""),
                    new_value=None,
                    severity="ended",
                    snapshot_date=snap_date,
                    detected_at=detected_at,
                )
            )
            continue
        # Provider in both — compare significant fields.
        assert old_rec is not None and new_rec is not None
        for field in SIGNIFICANT_FIELDS:
            ov = old_rec.get(field)
            nv = new_rec.get(field)
            sev = _classify(field, ov, nv)
            if sev == "unchanged":
                continue
            changes.append(
                Change(
                    provider_id=pid,
                    provider_name=new_rec.get("name", pid),
                    category=new_rec.get("category", ""),
                    field=field,
                    old_value=ov,
                    new_value=nv,
                    severity=sev,
                    snapshot_date=snap_date,
                    detected_at=detected_at,
                )
            )
    return changes


def compute_changes(
    *,
    limit: int = 200,
    since: str | None = None,
) -> ChangesResponse:
    """Walk all snapshots in date order, accumulate field-level changes.

    `since` (YYYY-MM-DD): only include changes whose `snapshot_date >= since`.
    Returns reverse-chronological (newest first), capped at `limit`.

    With only ONE snapshot present, returns empty changes — the seed
    snapshot itself isn't a "change" event. Changes start materializing
    once the daily cron writes its second snapshot.
    """
    dates = list_snapshots()
    if len(dates) < 2:
        return ChangesResponse(
            total=0,
            items=[],
            snapshot_dates=dates,
            latest_snapshot=dates[-1] if dates else None,
        )

    all_changes: list[Change] = []
    for old_d, new_d in zip(dates[:-1], dates[1:]):
        old = load_snapshot(old_d)
        new = load_snapshot(new_d)
        all_changes.extend(diff_snapshots(old, new, snap_date=new_d))

    if since is not None:
        all_changes = [c for c in all_changes if c.snapshot_date >= since]

    all_changes.sort(key=lambda c: (c.snapshot_date, c.detected_at), reverse=True)
    return ChangesResponse(
        total=len(all_changes),
        items=all_changes[:limit],
        snapshot_dates=dates,
        latest_snapshot=dates[-1],
    )


def seed_initial_snapshot_if_empty() -> str | None:
    """One-shot helper: if no snapshots exist, write today's snapshot
    from the v0.1 seed.json. Lets a fresh deploy serve the Changes tab
    with a sensible empty-state immediately, and gives the daily cron
    a baseline to diff against on its first run.

    Returns the snapshot date written, or None if snapshots already exist.
    """
    if list_snapshots():
        return None
    if not SEED_PATH.exists():
        return None
    with SEED_PATH.open(encoding="utf-8") as f:
        records = json.load(f)
    today = datetime.now(tz=timezone.utc).date()
    write_snapshot(records, snap_date=today)
    return today.isoformat()
