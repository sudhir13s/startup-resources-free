"""SqliteRepository behavior: real SQLite in tmp_path, never mocked."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from domain.runs import Candidate, RefreshOptions, RunReport, VerifyItem
from storage.repository import RunAlreadyActiveError
from storage.sqlite_repository import SqliteRepository


def _run(run_id: str = "r1") -> RunReport:
    return RunReport(run_id=run_id, trigger="test", options=RefreshOptions())


# --- save_provider: new / no-op / new version + changes ---


def test_should_store_new_version_when_provider_is_first_seen(repo, groq_record):
    result = repo.save_provider(groq_record, source="seed")
    assert result.stored is True
    assert result.version == 1
    assert [c.severity for c in result.changes] == ["new"]


def test_should_not_store_new_version_when_fingerprint_unchanged(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    result = repo.save_provider(groq_record, source="refresh")
    assert result.stored is False
    assert result.version == 1
    assert result.changes == []


def test_should_store_new_version_when_content_changes(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    changed = groq_record.model_copy(update={"headline": "New headline entirely"})
    result = repo.save_provider(changed, source="refresh", run_id="r1")
    assert result.stored is True
    assert result.version == 2
    assert len(result.changes) == 1
    assert result.changes[0].run_id == "r1"


def test_should_persist_field_changes_when_content_changes(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    changed = groq_record.model_copy(update={"headline": "Another headline"})
    repo.save_provider(changed, source="refresh", run_id="r9")
    changes = repo.list_changes()
    assert any(c.run_id == "r9" and c.field == "headline" for c in changes)


# --- freshness update on no-op save ---


def test_should_update_freshness_fields_when_fingerprint_unchanged(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    refreshed = groq_record.model_copy(
        update={"last_verified_at": date(2026, 9, 26), "parse_confidence": "high"}
    )
    result = repo.save_provider(refreshed, source="refresh")
    assert result.stored is False
    stored = repo.get_provider(groq_record.provider_id)
    assert stored.last_verified_at == date(2026, 9, 26)
    assert stored.parse_confidence == "high"


def test_should_not_add_history_row_when_only_freshness_changes(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    refreshed = groq_record.model_copy(update={"parse_confidence": "high"})
    repo.save_provider(refreshed, source="refresh")
    assert len(repo.history(groq_record.provider_id)) == 1


# --- history order + list_providers / get_provider ---


def test_should_return_history_newest_first(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    v2 = groq_record.model_copy(update={"headline": "v2 headline"})
    repo.save_provider(v2, source="refresh")
    v3 = groq_record.model_copy(update={"headline": "v3 headline"})
    repo.save_provider(v3, source="refresh")
    history = repo.history(groq_record.provider_id)
    assert [h.version for h in history] == [3, 2, 1]


def test_should_respect_history_limit(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    for i in range(5):
        repo.save_provider(
            groq_record.model_copy(update={"headline": f"headline {i}"}), source="refresh"
        )
    assert len(repo.history(groq_record.provider_id, limit=2)) == 2


def test_should_list_all_saved_providers(repo, sample_records):
    for record in sample_records:
        repo.save_provider(record, source="seed")
    assert {p.provider_id for p in repo.list_providers()} == {r.provider_id for r in sample_records}


def test_should_return_none_when_provider_missing(repo):
    assert repo.get_provider("does-not-exist") is None


# --- list_changes since filter ---


def test_should_filter_changes_since_a_date(repo, groq_record):
    repo.save_provider(groq_record, source="seed")
    far_future = datetime.now(tz=timezone.utc).date() + timedelta(days=365)
    changes = repo.list_changes(since=far_future)
    assert changes == []
    changes_all = repo.list_changes(since=date(2000, 1, 1))
    assert len(changes_all) == 1


# --- run lifecycle + active-run guard + stale run ---


def test_should_create_and_fetch_a_run(repo):
    repo.create_run(_run("r1"))
    fetched = repo.get_run("r1")
    assert fetched is not None
    assert fetched.status == "running"


def test_should_raise_when_a_run_is_already_active(repo):
    repo.create_run(_run("r1"))
    with pytest.raises(RunAlreadyActiveError):
        repo.create_run(_run("r2"))


def test_should_update_run_status(repo):
    repo.create_run(_run("r1"))
    finished = _run("r1").model_copy(update={"status": "succeeded", "finished_at": datetime.now(timezone.utc)})
    repo.update_run(finished)
    assert repo.get_run("r1").status == "succeeded"


def test_should_list_recent_runs(repo):
    repo.create_run(_run("r1"))
    repo.update_run(_run("r1").model_copy(update={"status": "succeeded"}))
    repo.create_run(_run("r2"))
    runs = repo.list_runs()
    assert {r.run_id for r in runs} == {"r1", "r2"}


def test_should_return_active_run_when_one_is_running(repo):
    repo.create_run(_run("r1"))
    active = repo.active_run()
    assert active is not None
    assert active.run_id == "r1"


def test_should_return_none_active_run_when_none_running(repo):
    repo.create_run(_run("r1"))
    repo.update_run(_run("r1").model_copy(update={"status": "succeeded"}))
    assert repo.active_run() is None


def test_should_allow_new_run_when_previous_running_run_is_stale(repo, tmp_path):
    repo.create_run(_run("r1"))
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    conn = sqlite3.connect(str(tmp_path / "resourceos.db"))
    conn.execute("UPDATE runs SET started_at = ? WHERE run_id = ?", (stale_time, "r1"))
    conn.commit()
    conn.close()
    repo.create_run(_run("r2"))
    stale = repo.get_run("r1")
    assert stale.status == "failed"
    assert "stale run" in stale.errors
    assert repo.get_run("r2").status == "running"


def test_should_not_treat_recent_running_run_as_stale(repo):
    repo.create_run(_run("r1"))
    with pytest.raises(RunAlreadyActiveError):
        repo.create_run(_run("r2"))
    assert repo.get_run("r1").status == "running"


# --- candidates ---


def test_should_insert_new_candidates(repo):
    candidate = Candidate(candidate_id="c1", url="https://x.com", domain="x.com", title="X")
    count = repo.add_candidates([candidate])
    assert count == 1
    assert [c.candidate_id for c in repo.list_candidates()] == ["c1"]


def test_should_dedupe_candidates_by_id(repo):
    candidate = Candidate(candidate_id="c1", url="https://x.com", domain="x.com", title="X")
    repo.add_candidates([candidate])
    count = repo.add_candidates([candidate])
    assert count == 0
    assert len(repo.list_candidates()) == 1


def test_should_update_candidate_status(repo):
    candidate = Candidate(candidate_id="c1", url="https://x.com", domain="x.com", title="X")
    repo.add_candidates([candidate])
    repo.set_candidate_status("c1", "approved")
    assert repo.list_candidates("pending") == []
    assert [c.status for c in repo.list_candidates("approved")] == ["approved"]


def test_should_list_all_candidates_when_status_is_none(repo):
    repo.add_candidates([Candidate(candidate_id="c1", url="https://x.com", domain="x.com", title="X")])
    repo.set_candidate_status("c1", "rejected")
    assert len(repo.list_candidates(status=None)) == 1


def test_should_noop_when_setting_status_of_unknown_candidate(repo):
    repo.set_candidate_status("does-not-exist", "approved")  # must not raise
    assert repo.list_candidates(status=None) == []


# --- verify queue (round-trips a nested ProviderRecord) ---


def test_should_enqueue_and_list_verify_item(repo, groq_record):
    item = VerifyItem(item_id="v1", provider_id=groq_record.provider_id, proposed=groq_record, reason="low confidence")
    repo.enqueue_verify(item)
    pending = repo.list_verify()
    assert [v.item_id for v in pending] == ["v1"]
    assert pending[0].proposed.provider_id == groq_record.provider_id


def test_should_update_verify_status(repo, groq_record):
    item = VerifyItem(item_id="v1", provider_id=groq_record.provider_id, proposed=groq_record, reason="low confidence")
    repo.enqueue_verify(item)
    repo.set_verify_status("v1", "accepted")
    assert repo.list_verify("pending") == []
    accepted = repo.list_verify("accepted")
    assert accepted[0].proposed.headline == groq_record.headline


def test_should_noop_when_setting_status_of_unknown_verify_item(repo):
    repo.set_verify_status("does-not-exist", "accepted")  # must not raise
    assert repo.list_verify(status=None) == []


def test_should_round_trip_provider_record_computed_fields_in_verify_item(repo, groq_record):
    """Regression: ProviderRecord's computed fields (categories, card_variant,
    india_accessible) must not leak into the stored JSON and break re-validation."""
    item = VerifyItem(item_id="v1", provider_id=groq_record.provider_id, proposed=groq_record, reason="x")
    repo.enqueue_verify(item)
    roundtripped = repo.list_verify()[0].proposed
    assert roundtripped.categories == groq_record.categories


# --- page hashes ---


def test_should_return_none_for_unknown_page_hash(repo):
    assert repo.get_page_hash("https://unseen.example") is None


def test_should_set_and_get_page_hash(repo):
    repo.set_page_hash("https://x.example", "hash-abc")
    assert repo.get_page_hash("https://x.example") == "hash-abc"


def test_should_overwrite_page_hash_on_update(repo):
    repo.set_page_hash("https://x.example", "hash-abc")
    repo.set_page_hash("https://x.example", "hash-def")
    assert repo.get_page_hash("https://x.example") == "hash-def"


# --- state blobs ---


def test_should_return_empty_dict_for_unknown_namespace(repo):
    assert repo.get_state("freellm") == {}


def test_should_put_and_get_state(repo):
    repo.put_state("freellm", {"groq": {"used": 5}})
    assert repo.get_state("freellm") == {"groq": {"used": 5}}


def test_should_overwrite_state_on_update(repo):
    repo.put_state("freellm", {"groq": {"used": 5}})
    repo.put_state("freellm", {"groq": {"used": 9}})
    assert repo.get_state("freellm") == {"groq": {"used": 9}}


# --- migrations idempotency (constructor applies them) ---


def test_should_not_reapply_migrations_on_reopen(tmp_path):
    path = tmp_path / "reopen.db"
    first = SqliteRepository(path)
    first.close()
    second = SqliteRepository(path)  # must not error re-creating tables
    second.close()


# --- snapshot_to (VACUUM INTO) ---


def test_should_write_a_snapshot_file(repo, groq_record, tmp_path):
    repo.save_provider(groq_record, source="seed")
    snapshot_path = tmp_path / "snapshot.db"
    repo.snapshot_to(snapshot_path)
    assert snapshot_path.exists()
    snapshot_repo = SqliteRepository(snapshot_path)
    assert snapshot_repo.get_provider(groq_record.provider_id) is not None
    snapshot_repo.close()
