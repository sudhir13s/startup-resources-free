"""seed_import.import_seed — idempotent load of the fixture into an empty repo."""

from __future__ import annotations

import json
from pathlib import Path

from storage.seed_import import import_seed

FIXTURE = Path(__file__).resolve().parent.parent.parent / "domain" / "fixtures" / "sample_records.json"


def test_should_import_every_record_when_repo_is_empty(repo):
    count = import_seed(repo, FIXTURE)
    assert count == 3
    assert {p.provider_id for p in repo.list_providers()} == {
        "aws-free-tier",
        "groq",
        "startup-india-seed-fund",
    }


def test_should_import_nothing_on_second_run(repo):
    import_seed(repo, FIXTURE)
    second_count = import_seed(repo, FIXTURE)
    assert second_count == 0
    assert len(repo.list_providers()) == 3


def test_should_only_import_missing_providers(repo, groq_record):
    repo.save_provider(groq_record, source="manual")
    count = import_seed(repo, FIXTURE)
    assert count == 2
    assert repo.history("groq")[0].source == "manual"


def test_should_mark_imported_rows_with_seed_source(repo):
    import_seed(repo, FIXTURE)
    history = repo.history("groq")
    assert history[0].source == "seed"


def _write_seed_with_groq_headline(tmp_path: Path, headline: str) -> Path:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in rows:
        if row["provider_id"] == "groq":
            row["headline"] = headline
    edited = tmp_path / "seed.json"
    edited.write_text(json.dumps(rows), encoding="utf-8")
    return edited


def test_should_apply_seed_correction_when_seed_entry_changed(repo, tmp_path):
    import_seed(repo, FIXTURE)
    edited = _write_seed_with_groq_headline(tmp_path, "Corrected headline")

    count = import_seed(repo, edited)

    assert count == 1
    assert repo.get_provider("groq").headline == "Corrected headline"
    assert any(c.field == "headline" for c in repo.list_changes())


def test_should_keep_refreshed_data_when_seed_entry_unchanged(repo, groq_record):
    import_seed(repo, FIXTURE)
    refreshed = groq_record.model_copy(update={"headline": "Learned by refresh"})
    repo.save_provider(refreshed, source="refresh")

    count = import_seed(repo, FIXTURE)

    assert count == 0
    assert repo.get_provider("groq").headline == "Learned by refresh"
