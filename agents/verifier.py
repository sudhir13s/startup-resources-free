"""Verifier — pushes low-confidence ProviderRecord rows into a queue
that humans (or the dashboard's Verify tab) can resolve.

v0.2 storage: append-only JSONL file at
`${VERIFY_QUEUE_DIR}/queue.jsonl` (default `data/verify-queue/queue.jsonl`).
Each line is a self-contained JSON object — survives crashes; `tail -f`
during a run shows live drops.

B3 swaps the storage to SQLite via `backend/db.py` while keeping the
public API (`queue_low_confidence`, `pending_items`, `resolve`).
That way callers don't change.

Confirm/Reject flow used by the dashboard's verify tab will live in B9
(`/api/verify-queue/<id>/{confirm,reject}`) — this module only writes
the queue. The API + UI consume it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from schema.records import ProviderRecord


VerifyStatus = Literal["pending", "confirmed", "rejected"]


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
    if status not in ("confirmed", "rejected"):
        raise ValueError(f"resolve() status must be confirmed|rejected, got {status!r}")

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
