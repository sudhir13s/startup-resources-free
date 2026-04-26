from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import snapshots  # noqa: E402


# ---------- list/load ----------


def test_list_snapshots_returns_dates_in_ascending_order(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-03-01.json").write_text("[]")
    (tmp_path / "2026-04-26.json").write_text("[]")
    (tmp_path / "2026-01-15.json").write_text("[]")
    (tmp_path / "not-a-date.json").write_text("[]")  # ignored
    assert snapshots.list_snapshots() == ["2026-01-15", "2026-03-01", "2026-04-26"]


def test_load_snapshot_returns_records(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-04-26.json").write_text(json.dumps([{"id": "a", "name": "A"}]))
    rows = snapshots.load_snapshot("2026-04-26")
    assert rows == [{"id": "a", "name": "A"}]


def test_write_snapshot_atomic(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    out = snapshots.write_snapshot([{"id": "x"}], snap_date=date(2026, 5, 1))
    assert out.exists()
    assert json.loads(out.read_text()) == [{"id": "x"}]


# ---------- diff ----------


def _rec(**kw):
    base = {
        "id": kw.get("id", "p1"),
        "name": kw.get("name", "Provider"),
        "category": kw.get("category", "ai-api"),
        "headline": kw.get("headline", "headline"),
        "free_tier_summary": kw.get("free_tier_summary", "summary"),
        "quota_summary": kw.get("quota_summary", "100 req/day"),
        "duration_summary": kw.get("duration_summary", "always free"),
        "region_summary": kw.get("region_summary", "Global"),
        "offer_type": kw.get("offer_type", "free-quota"),
        "eligibility_summary": kw.get("eligibility_summary", "Any user"),
        "use_case_tiers": kw.get("use_case_tiers", ["hobby"]),
        "india_accessible": kw.get("india_accessible", True),
        "geo_priority": kw.get("geo_priority", "global-other"),
        "parse_confidence": kw.get("parse_confidence", "high"),
    }
    return base


def test_diff_detects_new_provider():
    old: list[dict] = []
    new = [_rec(id="p1")]
    changes = snapshots.diff_snapshots(old, new, snap_date="2026-04-26")
    assert any(c.severity == "new" and c.provider_id == "p1" for c in changes)


def test_diff_detects_ended_provider():
    old = [_rec(id="p1")]
    new: list[dict] = []
    changes = snapshots.diff_snapshots(old, new, snap_date="2026-04-26")
    assert any(c.severity == "ended" and c.provider_id == "p1" for c in changes)


def test_diff_detects_quota_reduction():
    old = [_rec(id="p1", quota_summary="14,400 req/day")]
    new = [_rec(id="p1", quota_summary="1,000 req/day")]
    changes = snapshots.diff_snapshots(old, new, snap_date="2026-04-26")
    quota_changes = [c for c in changes if c.field == "quota_summary"]
    assert len(quota_changes) == 1
    assert quota_changes[0].severity == "reduced"


def test_diff_detects_quota_improvement():
    old = [_rec(id="p1", quota_summary="1,000 req/day")]
    new = [_rec(id="p1", quota_summary="14,400 req/day")]
    changes = snapshots.diff_snapshots(old, new, snap_date="2026-04-26")
    quota_changes = [c for c in changes if c.field == "quota_summary"]
    assert quota_changes[0].severity == "improved"


def test_diff_skips_unchanged_records():
    rec = _rec(id="p1")
    changes = snapshots.diff_snapshots([rec], [rec], snap_date="2026-04-26")
    # Identical input -> no changes
    assert changes == []


def test_diff_does_not_emit_for_insignificant_fields():
    """`scraped_at` and similar metadata aren't in SIGNIFICANT_FIELDS."""
    old = _rec(id="p1")
    new = _rec(id="p1")
    new_copy = {**new, "scraped_at": "2026-04-26T01:00:00Z"}
    old_copy = {**old, "scraped_at": "2026-04-25T01:00:00Z"}
    changes = snapshots.diff_snapshots([old_copy], [new_copy], snap_date="2026-04-26")
    assert changes == []


# ---------- compute_changes ----------


def test_compute_changes_empty_when_only_one_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-04-26.json").write_text(json.dumps([_rec(id="p1")]))
    resp = snapshots.compute_changes()
    assert resp.total == 0
    assert resp.snapshot_dates == ["2026-04-26"]
    assert resp.latest_snapshot == "2026-04-26"


def test_compute_changes_diffs_two_snapshots(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-04-25.json").write_text(
        json.dumps([_rec(id="p1", quota_summary="14,400 req/day")])
    )
    (tmp_path / "2026-04-26.json").write_text(
        json.dumps([_rec(id="p1", quota_summary="1,000 req/day")])
    )
    resp = snapshots.compute_changes()
    assert resp.total >= 1
    assert any(c.severity == "reduced" for c in resp.items)
    assert resp.latest_snapshot == "2026-04-26"


def test_compute_changes_reverse_chronological(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-04-25.json").write_text(json.dumps([_rec(id="p1")]))
    (tmp_path / "2026-04-26.json").write_text(json.dumps([_rec(id="p1", headline="new")]))
    (tmp_path / "2026-04-27.json").write_text(json.dumps([_rec(id="p1", headline="newer")]))
    resp = snapshots.compute_changes()
    dates = [c.snapshot_date for c in resp.items]
    assert dates == sorted(dates, reverse=True)


def test_compute_changes_since_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-04-20.json").write_text(json.dumps([_rec(id="p1")]))
    (tmp_path / "2026-04-25.json").write_text(json.dumps([_rec(id="p1", headline="b")]))
    (tmp_path / "2026-04-26.json").write_text(json.dumps([_rec(id="p1", headline="c")]))
    resp = snapshots.compute_changes(since="2026-04-26")
    assert all(c.snapshot_date >= "2026-04-26" for c in resp.items)


# ---------- seed_initial_snapshot_if_empty ----------


def test_seed_initial_snapshot_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshots, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(
        snapshots, "SEED_PATH", tmp_path / "_seed.json", raising=False
    )
    (tmp_path / "_seed.json").write_text(json.dumps([_rec(id="p1")]))
    first = snapshots.seed_initial_snapshot_if_empty()
    assert first is not None
    second = snapshots.seed_initial_snapshot_if_empty()
    assert second is None  # already seeded -> no-op
