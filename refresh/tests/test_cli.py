from __future__ import annotations

import json
from pathlib import Path

import pytest

from refresh.__main__ import main


@pytest.fixture
def seed_path(tmp_path: Path) -> Path:
    path = tmp_path / "seed.json"
    path.write_text(
        json.dumps(
            [
                {
                    "provider_id": "test-provider",
                    "name": "Test Provider",
                    "vendor": "Test Co",
                    "category": "cloud",
                    "source_urls": ["https://example.com/pricing"],
                    "offer_type": "free-tier",
                    "headline": "A free offer",
                    "use_case_tiers": ["hobby"],
                    "parse_confidence": "medium",
                }
            ]
        )
    )
    return path


def test_should_run_refresh_and_print_report(tmp_path: Path, seed_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path / "freellm-quotas"))
    db_path = tmp_path / "resourceos.db"

    exit_code = main(
        [
            "run",
            "--db",
            str(db_path),
            "--seed",
            str(seed_path),
            "--providers",
            "does-not-exist",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "run_id=" in captured.out
    assert "status=" in captured.out


def test_should_print_search_status(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    db_path = tmp_path / "resourceos.db"

    exit_code = main(["search-status", "--db", str(db_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "providers_active" in captured.out


def test_should_print_help_when_no_command(capsys):
    with pytest.raises(SystemExit):
        main([])
