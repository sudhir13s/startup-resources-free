"""seed_import.import_seed — idempotent load of the fixture into an empty repo."""

from __future__ import annotations

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
