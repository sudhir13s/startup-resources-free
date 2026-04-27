"""verifier — file-backed queue of low-confidence records."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from agents.verifier import (
    all_items,
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
