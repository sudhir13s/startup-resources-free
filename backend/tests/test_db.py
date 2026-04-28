"""SQLite persistence layer."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from agents.change_detector import ChangeReport
from agents.verifier import VerifyItem
from backend import db as db_module
from schema.records import ProviderRecord


def _verify_item(*, record_id: str, queued_at: datetime) -> VerifyItem:
    return VerifyItem(
        record_id=record_id,
        provider_id=record_id,
        provider_name=record_id.upper(),
        source_url=f"https://{record_id}.test/",
        parse_confidence="low",
        reason="missing",
        queued_at=queued_at.isoformat(),
        record_payload={"id": record_id},
    )


def _record(**overrides) -> ProviderRecord:
    base = dict(
        id="rec-1",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.com/pricing",
        offer_type="free-tier",
        offer_summary="Free Web Services with 750 hrs/month.",
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 27),
    )
    base.update(overrides)
    return ProviderRecord(**base)


@pytest.fixture
def conn(tmp_path: Path):
    """Fresh SQLite DB per test, migrations applied."""
    path = tmp_path / "test.db"
    c = db_module.connect(path)
    db_module.apply_migrations(c)
    yield c
    c.close()


# ---------- migrations ----------


def test_apply_migrations_is_idempotent(tmp_path: Path):
    path = tmp_path / "x.db"
    c = db_module.connect(path)
    first = db_module.apply_migrations(c)
    second = db_module.apply_migrations(c)
    assert 1 in first
    assert second == []  # nothing new to apply


def test_schema_version_recorded(conn):
    versions = db_module.applied_versions(conn)
    assert 1 in versions


# ---------- ProviderRecord round-trip ----------


def test_insert_and_get_record(conn):
    record = _record(id="abc", limits={"bw_gb": 100})
    inserted = db_module.insert_record(conn, record)
    assert inserted is True

    got = db_module.get_record(conn, "abc")
    assert got is not None
    assert got.provider_id == "render"
    assert got.limits == {"bw_gb": 100}
    assert got.india_accessible is True


def test_insert_record_idempotent_on_id(conn):
    record = _record(id="dup")
    assert db_module.insert_record(conn, record) is True
    assert db_module.insert_record(conn, record) is False


def test_latest_records_returns_one_per_provider_id(conn):
    older = _record(
        id="older",
        provider_id="render",
        scraped_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    newer = _record(
        id="newer",
        provider_id="render",
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )
    other = _record(
        id="other",
        provider_id="vercel",
        provider_name="Vercel",
        source_url="https://vercel.com/pricing",
    )
    db_module.insert_records(conn, [older, newer, other])
    latest = db_module.latest_records(conn)
    ids = sorted(r.id for r in latest)
    assert ids == ["newer", "other"]


def test_history_for_returns_descending(conn):
    rows = [
        _record(
            id=f"r-{i}",
            scraped_at=datetime(2026, 4, 20 + i, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    db_module.insert_records(conn, rows)
    history = db_module.history_for(conn, "render")
    assert [r.id for r in history] == ["r-2", "r-1", "r-0"]


def test_latest_for_returns_most_recent(conn):
    rows = [
        _record(
            id=f"r-{i}",
            scraped_at=datetime(2026, 4, 20 + i, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    db_module.insert_records(conn, rows)
    got = db_module.latest_for(conn, "render")
    assert got is not None
    assert got.id == "r-2"


def test_latest_for_unknown_provider_returns_none(conn):
    assert db_module.latest_for(conn, "nope") is None


# ---------- change_reports ----------


def test_insert_change_assigns_id(conn):
    report = ChangeReport(
        provider_id="render",
        severity="reduced",
        changed_fields=["quota_summary"],
        summary="quota dropped",
        today_id="t",
        yesterday_id="y",
    )
    new_id = db_module.insert_change(conn, report)
    assert new_id > 0


def test_latest_changes_filters_by_severity(conn):
    db_module.insert_changes(
        conn,
        [
            ChangeReport(provider_id="a", severity="reduced", summary="r"),
            ChangeReport(provider_id="b", severity="improved", summary="i"),
            ChangeReport(provider_id="c", severity="reduced", summary="r2"),
        ],
    )
    reduced = db_module.latest_changes(conn, severity="reduced")
    assert len(reduced) == 2
    assert all(r["severity"] == "reduced" for r in reduced)


# ---------- verify queue ----------


def test_enqueue_verify_idempotent_on_record_id(conn):
    item = VerifyItem(
        record_id="rec-x",
        provider_id="x",
        provider_name="X",
        source_url="https://x.test/",
        parse_confidence="low",
        reason="missing",
        queued_at=datetime.now(tz=timezone.utc).isoformat(),
        record_payload={"id": "rec-x"},
    )
    assert db_module.enqueue_verify(conn, item) is True
    assert db_module.enqueue_verify(conn, item) is False
    pending = db_module.pending_verify(conn)
    assert len(pending) == 1


def test_resolve_verify_flips_status_and_only_pending(conn):
    item = VerifyItem(
        record_id="rec-y",
        provider_id="y",
        provider_name="Y",
        source_url="https://y.test/",
        parse_confidence="low",
        reason="missing",
        queued_at=datetime.now(tz=timezone.utc).isoformat(),
        record_payload={"id": "rec-y"},
    )
    db_module.enqueue_verify(conn, item)
    ok = db_module.resolve_verify(conn, "rec-y", status="confirmed", resolved_by="me")
    assert ok is True
    # Resolving a non-pending row is a no-op.
    again = db_module.resolve_verify(conn, "rec-y", status="rejected")
    assert again is False
    assert db_module.pending_verify(conn) == []


def test_resolve_verify_rejects_invalid_status(conn):
    with pytest.raises(ValueError):
        db_module.resolve_verify(conn, "x", status="pending")


# ---------- env override ----------


def test_db_path_honors_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    custom = tmp_path / "alt.db"
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(custom))
    assert db_module.db_path() == custom


# ---------- shape sanity ----------


def test_record_round_trips_eligibility_and_tiers(conn):
    record = _record(
        id="full",
        use_case_tiers=["hobby", "personal"],
        tier_fit_rationale="fits both",
    )
    db_module.insert_record(conn, record)
    got = db_module.get_record(conn, "full")
    assert got is not None
    assert got.use_case_tiers == ["hobby", "personal"]
    assert got.tier_fit_rationale == "fits both"

    # eligibility_json round-trips.
    raw = conn.execute(
        "SELECT eligibility_json FROM provider_records WHERE id = ?", ("full",)
    ).fetchone()
    payload = json.loads(raw["eligibility_json"])
    assert payload["regions"] == ["global"]
    assert payload["user_types"] == ["any"]


# =============================================================================
# auto_expire_verify — Sprint #4 / architect CRITICAL #6 (2026-04-28).
# =============================================================================


def test_auto_expire_verify_flips_old_pending_rows(conn):
    now = datetime.now(tz=timezone.utc)
    old = _verify_item(record_id="old", queued_at=now - timedelta(days=45))
    fresh = _verify_item(record_id="fresh", queued_at=now - timedelta(days=2))
    db_module.enqueue_verify(conn, old)
    db_module.enqueue_verify(conn, fresh)

    expired = db_module.auto_expire_verify(conn, days=30)
    assert expired == 1

    row = conn.execute(
        "SELECT status, resolved_at, resolved_by FROM verify_queue WHERE record_id = ?",
        ("old",),
    ).fetchone()
    assert row["status"] == "expired"
    assert row["resolved_by"] == "auto-expire"
    assert row["resolved_at"] is not None

    fresh_row = conn.execute(
        "SELECT status FROM verify_queue WHERE record_id = ?", ("fresh",)
    ).fetchone()
    assert fresh_row["status"] == "pending"


def test_auto_expire_verify_does_not_touch_resolved_rows(conn):
    now = datetime.now(tz=timezone.utc)
    item = _verify_item(record_id="done", queued_at=now - timedelta(days=120))
    db_module.enqueue_verify(conn, item)
    db_module.resolve_verify(conn, "done", status="confirmed", resolved_by="curator")

    expired = db_module.auto_expire_verify(conn, days=30)
    assert expired == 0

    row = conn.execute(
        "SELECT status, resolved_by FROM verify_queue WHERE record_id = ?",
        ("done",),
    ).fetchone()
    assert row["status"] == "confirmed"
    assert row["resolved_by"] == "curator"


def test_auto_expire_verify_respects_days_param(conn):
    now = datetime.now(tz=timezone.utc)
    item = _verify_item(record_id="middling", queued_at=now - timedelta(days=10))
    db_module.enqueue_verify(conn, item)

    # 30-day TTL leaves it pending.
    assert db_module.auto_expire_verify(conn, days=30) == 0
    pending = db_module.pending_verify(conn)
    assert {p["record_id"] for p in pending} == {"middling"}

    # 7-day TTL flips it.
    assert db_module.auto_expire_verify(conn, days=7) == 1
    assert db_module.pending_verify(conn) == []


def test_auto_expire_verify_returns_zero_on_empty_queue(conn):
    assert db_module.auto_expire_verify(conn, days=30) == 0


def test_auto_expire_verify_is_idempotent(conn):
    now = datetime.now(tz=timezone.utc)
    item = _verify_item(record_id="r", queued_at=now - timedelta(days=60))
    db_module.enqueue_verify(conn, item)

    assert db_module.auto_expire_verify(conn, days=30) == 1
    # Second sweep finds nothing because the row is already in `expired`.
    assert db_module.auto_expire_verify(conn, days=30) == 0


def test_auto_expire_verify_rejects_non_positive_days(conn):
    with pytest.raises(ValueError):
        db_module.auto_expire_verify(conn, days=0)
    with pytest.raises(ValueError):
        db_module.auto_expire_verify(conn, days=-1)


def test_resolve_verify_now_accepts_expired_status(conn):
    """`resolve_verify` validator must allow `expired` so manual sweeps work too."""
    now = datetime.now(tz=timezone.utc)
    item = _verify_item(record_id="manual", queued_at=now)
    db_module.enqueue_verify(conn, item)

    ok = db_module.resolve_verify(conn, "manual", status="expired", resolved_by="ops")
    assert ok is True
    row = conn.execute(
        "SELECT status, resolved_by FROM verify_queue WHERE record_id = ?",
        ("manual",),
    ).fetchone()
    assert row["status"] == "expired"
    assert row["resolved_by"] == "ops"
