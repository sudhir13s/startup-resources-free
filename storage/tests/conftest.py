"""Shared fixtures for storage tests. Real SQLite in tmp_path — never mocked."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.records import ProviderRecord
from storage.sqlite_repository import SqliteRepository

FIXTURE = Path(__file__).resolve().parent.parent.parent / "domain" / "fixtures" / "sample_records.json"


@pytest.fixture
def repo(tmp_path) -> SqliteRepository:
    instance = SqliteRepository(tmp_path / "resourceos.db")
    yield instance
    instance.close()


@pytest.fixture
def sample_records() -> list[ProviderRecord]:
    return [ProviderRecord.model_validate(row) for row in json.loads(FIXTURE.read_text())]


@pytest.fixture
def groq_record(sample_records: list[ProviderRecord]) -> ProviderRecord:
    return next(r for r in sample_records if r.provider_id == "groq")
