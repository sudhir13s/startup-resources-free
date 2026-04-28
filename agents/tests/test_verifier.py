"""verifier — file-backed queue of low-confidence records."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from agents import verifier as verifier_module
from agents.verifier import (
    AUTO_EXPIRE_RESOLVER,
    all_items,
    auto_expire,
    pending_items,
    queue_low_confidence,
    queue_many,
    resolve,
)
from schema.records import ProviderRecord


def _record(**overrides) -> ProviderRecord:
    base = dict(
        id="rec-1",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.com/pricing",
        offer_type="free-tier",
        offer_summary="Free 750 hrs.",
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        parse_confidence="low",
        source_method="llm",
        last_verified_at=date(2026, 4, 27),
    )
    base.update(overrides)
    return ProviderRecord(**base)


def test_queue_writes_one_pending_item():
    record = _record()
    item = queue_low_confidence(record, reason="missing fields")
    assert item.status == "pending"
    assert item.record_id == record.id
    assert item.reason == "missing fields"

    pending = pending_items()
    assert len(pending) == 1
    assert pending[0].record_id == record.id


def test_queue_is_idempotent_on_record_id():
    record = _record(id="dup")
    queue_low_confidence(record, reason="first")
    queue_low_confidence(record, reason="second-attempt")
    pending = pending_items()
    assert len(pending) == 1
    # First wins.
    assert pending[0].reason == "first"


def test_resolve_confirms_pending_item():
    record = _record(id="conf")
    queue_low_confidence(record, reason="x")
    resolved = resolve("conf", status="confirmed", resolved_by="curator")
    assert resolved is not None
    assert resolved.status == "confirmed"
    assert resolved.resolved_by == "curator"
    assert pending_items() == []
    assert len(all_items()) == 1


def test_resolve_returns_none_for_unknown_id():
    out = resolve("does-not-exist", status="rejected")
    assert out is None


def test_resolve_rejects_invalid_status():
    record = _record(id="invalid-status")
    queue_low_confidence(record, reason="x")
    with pytest.raises(ValueError):
        resolve("invalid-status", status="pending")  # type: ignore[arg-type]


def test_queue_many_round_trip():
    pairs = [
        (_record(id=f"r-{i}", provider_id=f"p-{i}"), f"reason-{i}")
        for i in range(3)
    ]
    out = queue_many(pairs)
    assert len(out) == 3
    assert all(item.status == "pending" for item in out)
    assert {i.provider_id for i in pending_items()} == {"p-0", "p-1", "p-2"}


# =============================================================================
# auto_expire — Sprint #4 / architect CRITICAL #6 (2026-04-28).
#
# With the /verify UI killed in Sprint #3, low-confidence rows have no
# resolution path. Without a TTL sweep they accumulate forever on
# Render's free disk. These tests cover the JSONL side; SQLite coverage
# lives in backend/tests/test_db.py::auto_expire_verify.
# =============================================================================


def _backdate_jsonl(path, record_id: str, *, days_ago: int) -> None:
    """Rewrite the JSONL queue so a single row's `queued_at` is `days_ago`
    days in the past. Easier than monkey-patching the clock."""
    backdated = (
        datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    ).isoformat()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload["record_id"] == record_id:
            payload["queued_at"] = backdated
        rows.append(payload)
    with path.open("w", encoding="utf-8") as f:
        for payload in rows:
            f.write(json.dumps(payload) + "\n")


def test_auto_expire_flips_rows_older_than_default_ttl():
    queue_low_confidence(_record(id="old"), reason="stale")
    _backdate_jsonl(verifier_module._queue_path(), "old", days_ago=45)

    expired = auto_expire()
    assert expired == 1
    assert pending_items() == []
    aged = next(i for i in all_items() if i.record_id == "old")
    assert aged.status == "expired"
    assert aged.resolved_by == AUTO_EXPIRE_RESOLVER
    assert aged.resolved_at is not None


def test_auto_expire_leaves_recent_rows_pending():
    queue_low_confidence(_record(id="fresh"), reason="just now")
    expired = auto_expire()
    assert expired == 0
    assert {i.record_id for i in pending_items()} == {"fresh"}


def test_auto_expire_does_not_touch_resolved_rows():
    """A row already confirmed/rejected must not be re-flipped to expired."""
    queue_low_confidence(_record(id="done"), reason="x")
    resolve("done", status="confirmed", resolved_by="curator")
    _backdate_jsonl(verifier_module._queue_path(), "done", days_ago=120)

    expired = auto_expire()
    assert expired == 0
    settled = next(i for i in all_items() if i.record_id == "done")
    assert settled.status == "confirmed"
    assert settled.resolved_by == "curator"


def test_auto_expire_respects_custom_days_param():
    queue_low_confidence(_record(id="medium"), reason="x")
    _backdate_jsonl(verifier_module._queue_path(), "medium", days_ago=10)

    # 30-day TTL leaves it pending …
    assert auto_expire(days=30) == 0
    assert {i.record_id for i in pending_items()} == {"medium"}

    # … but a 7-day TTL flips it.
    assert auto_expire(days=7) == 1
    assert pending_items() == []


def test_auto_expire_rejects_non_positive_days():
    with pytest.raises(ValueError):
        auto_expire(days=0)
    with pytest.raises(ValueError):
        auto_expire(days=-5)


def test_auto_expire_returns_zero_when_queue_missing(tmp_path, monkeypatch):
    """Pipeline calls auto_expire even on first-ever run before queue.jsonl exists."""
    empty = tmp_path / "no-queue-here"
    monkeypatch.setenv("VERIFY_QUEUE_DIR", str(empty))
    assert auto_expire() == 0


def test_auto_expire_logs_structured_event(caplog):
    queue_low_confidence(_record(id="logged"), reason="x")
    _backdate_jsonl(verifier_module._queue_path(), "logged", days_ago=60)

    with caplog.at_level(logging.INFO, logger="agents.verifier"):
        count = auto_expire(days=30)

    assert count == 1
    matching = [
        r for r in caplog.records if r.name == "agents.verifier"
    ]
    assert matching, "expected a log line on agents.verifier logger"
    payload = matching[-1]
    assert getattr(payload, "event", None) == "verify_auto_expire"
    assert getattr(payload, "expired_count", None) == 1
    assert getattr(payload, "ttl_days", None) == 30


def test_auto_expire_status_round_trips_through_resolve():
    """`resolve` must accept `expired` so callers can mark rows manually too."""
    queue_low_confidence(_record(id="manual-expire"), reason="x")
    out = resolve("manual-expire", status="expired", resolved_by="ops")
    assert out is not None
    assert out.status == "expired"
    assert out.resolved_by == "ops"
