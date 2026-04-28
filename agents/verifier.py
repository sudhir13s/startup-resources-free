"""Verifier — pushes low-confidence ProviderRecord rows into a queue
that humans (or the dashboard's Verify tab) can resolve.

v0.2 storage: append-only JSONL file at
`${VERIFY_QUEUE_DIR}/queue.jsonl` (default `data/verify-queue/queue.jsonl`).
Each line is a self-contained JSON object — survives crashes; `tail -f`
during a run shows live drops.

B3 swaps the storage to SQLite via `backend/db.py` while keeping the
public API (`queue_low_confidence`, `pending_items`, `resolve`).
That way callers don't change.

Note: the orchestrator currently writes to BOTH stores — JSONL via
`queue_low_confidence` (for legacy/local debugging) and SQLite via
`backend.db.enqueue_verify` (for the API). `auto_expire()` therefore
sweeps both; either one alone would leak rows on the other side.

Confirm/Reject flow used by the dashboard's verify tab landed in B9
(`/api/verify-queue/<id>/{confirm,reject}`). Sprint #3 retires that
UI/API; Sprint #4 (this file) adds a 30-day auto-expire so rows that
no longer have a resolution path don't accumulate forever on Render's
free disk. Closes architect roundtable CRITICAL #6 (2026-04-28).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Literal

from schema.records import ProviderRecord


logger = logging.getLogger("agents.verifier")


VerifyStatus = Literal["pending", "confirmed", "rejected", "expired"]


# Sentinel `resolved_by` value attached to rows expired by `auto_expire()`.
# Lets human review distinguish auto-expired rows from human-resolved ones.
AUTO_EXPIRE_RESOLVER = "auto-expire"


@dataclass
class VerifyItem:
    """One queue entry. Mirrors what the API + UI render."""

    record_id: str
    provider_id: str
    provider_name: str
    source_url: str
    parse_confidence: str
    reason: str  # short human label: "missing required fields", "json-parse-failed"
    queued_at: str  # UTC ISO 8601
    record_payload: dict = field(default_factory=dict)
    status: VerifyStatus = "pending"
    resolved_at: str | None = None
    resolved_by: str | None = None  # username when humans wire in B9


def _queue_path() -> Path:
    base = os.environ.get("VERIFY_QUEUE_DIR")
    return (Path(base) if base else Path("data/verify-queue")) / "queue.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def queue_low_confidence(
    record: ProviderRecord,
    *,
    reason: str,
) -> VerifyItem:
    """Append a low-confidence record to the verify queue.

    Idempotent on `record.id` — if a row with the same id is already
    queued in `pending` status, this is a no-op and returns the
    existing item.
    """
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Idempotency: scan existing pending entries for the same record_id.
    for existing in pending_items():
        if existing.record_id == record.id:
            return existing

    item = VerifyItem(
        record_id=record.id,
        provider_id=record.provider_id,
        provider_name=record.provider_name,
        source_url=record.source_url,
        parse_confidence=record.parse_confidence,
        reason=reason,
        queued_at=_utcnow_iso(),
        record_payload=record.model_dump(mode="json"),
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(item), default=str) + "\n")
    return item


def all_items() -> list[VerifyItem]:
    """Read all queue entries (every status). Newest last."""
    path = _queue_path()
    if not path.exists():
        return []
    items: list[VerifyItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            items.append(VerifyItem(**payload))
    return items


def pending_items() -> list[VerifyItem]:
    return [i for i in all_items() if i.status == "pending"]


def resolve(
    record_id: str,
    *,
    status: VerifyStatus,
    resolved_by: str | None = None,
) -> VerifyItem | None:
    """Mark the most-recent pending entry for `record_id` as resolved.

    Implementation: rewrites the JSONL file with the entry status
    flipped. The file is small (low-confidence rows only) so a full
    rewrite is fine. B3's SQLite swap eliminates this O(n) cost.
    """
    if status not in ("confirmed", "rejected", "expired"):
        raise ValueError(
            f"resolve() status must be confirmed|rejected|expired, got {status!r}"
        )

    items = all_items()
    target_idx: int | None = None
    for idx, item in enumerate(items):
        if item.record_id == record_id and item.status == "pending":
            target_idx = idx  # keep latest match
    if target_idx is None:
        return None

    items[target_idx].status = status
    items[target_idx].resolved_at = _utcnow_iso()
    items[target_idx].resolved_by = resolved_by

    path = _queue_path()
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(asdict(item), default=str) + "\n")
    return items[target_idx]


def queue_many(items: Iterable[tuple[ProviderRecord, str]]) -> list[VerifyItem]:
    """Convenience: queue multiple `(record, reason)` pairs."""
    return [queue_low_confidence(r, reason=reason) for r, reason in items]


def _parse_queued_at(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None when malformed.

    Defensive: a hand-edited JSONL row should not crash the sweep.
    """
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        # Treat naive timestamps as UTC (the writer always emits UTC).
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _auto_expire_jsonl(*, cutoff: datetime, now_iso: str) -> int:
    """Sweep the JSONL queue. Returns the count of rows expired."""
    path = _queue_path()
    if not path.exists():
        return 0
    items = all_items()
    expired = 0
    for item in items:
        if item.status != "pending":
            continue
        queued_at = _parse_queued_at(item.queued_at)
        if queued_at is None or queued_at >= cutoff:
            continue
        item.status = "expired"
        item.resolved_at = now_iso
        item.resolved_by = AUTO_EXPIRE_RESOLVER
        expired += 1
    if expired:
        with path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(asdict(item), default=str) + "\n")
    return expired


def _auto_expire_sqlite(*, days: int) -> int:
    """Sweep the SQLite queue if a DB exists. Returns the count expired.

    Looks at `RESOURCEOS_DB_PATH` env first; falls back to the default
    `backend.db.DEFAULT_DB_PATH`. If neither file exists, returns 0
    without touching disk. We import lazily so this module stays
    importable without `backend/` on sys.path (e.g. pure-JSONL flows).
    """
    raw = os.environ.get("RESOURCEOS_DB_PATH")
    try:
        from backend import db as db_module  # local import — avoids cycle
    except ImportError:
        return 0

    target = Path(raw) if raw else db_module.DEFAULT_DB_PATH
    if not target.exists():
        return 0
    try:
        with db_module.db_session(target) as conn:
            return db_module.auto_expire_verify(conn, days=days)
    except Exception:  # noqa: BLE001 — sweep is best-effort, never crash pipeline
        logger.exception("verify_auto_expire_sqlite_failed", extra={"db": str(target)})
        return 0


def auto_expire(*, days: int = 30) -> int:
    """Mark every `pending` verify-queue row older than `days` days as `expired`.

    Sweeps BOTH storage layers — the JSONL file (legacy) AND the SQLite
    `verify_queue` table (live). The orchestrator writes to both today,
    so a single-store sweep would leak rows on the other side. The
    architect's 2026-04-28 roundtable explicitly flagged this dual-write.

    Idempotent: rows already in `expired` / `confirmed` / `rejected`
    status are untouched.

    Returns the total number of rows transitioned across both stores.
    """
    if days <= 0:
        raise ValueError(f"days must be a positive integer, got {days}")

    now = datetime.now(tz=timezone.utc)
    now_iso = now.isoformat()
    cutoff = now - timedelta(days=days)

    jsonl_count = _auto_expire_jsonl(cutoff=cutoff, now_iso=now_iso)
    sqlite_count = _auto_expire_sqlite(days=days)
    total = jsonl_count + sqlite_count

    logger.info(
        "verify_auto_expire",
        extra={
            "event": "verify_auto_expire",
            "expired_count": total,
            "jsonl_expired": jsonl_count,
            "sqlite_expired": sqlite_count,
            "ttl_days": days,
        },
    )
    return total
