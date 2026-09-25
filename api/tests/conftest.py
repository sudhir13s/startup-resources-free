"""Shared fixtures: a real SqliteRepository seeded from the domain fixture,
a fake refresh runner (the injected boundary per `refresh/contracts.py`),
and a fake `R2DataSync`-shaped push target — never mocks of the
repository itself.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.auth import derive_api_key
from api.main import create_app
from api.settings import Settings
from domain.records import ProviderRecord
from domain.runs import RunReport
from storage.sqlite_repository import SqliteRepository

FIXTURE = Path(__file__).resolve().parent.parent.parent / "domain" / "fixtures" / "sample_records.json"
RESOURCEOS_PASSWORD = "test-admin-token"  # noqa: S105 - fixture constant, not a real secret


@pytest.fixture
def sample_records() -> list[ProviderRecord]:
    return [ProviderRecord.model_validate(row) for row in json.loads(FIXTURE.read_text())]


@pytest.fixture
def seed_file(tmp_path: Path, sample_records: list[ProviderRecord]) -> Path:
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([r.to_storage() for r in sample_records]))
    return path


@pytest.fixture
def repository(tmp_path: Path) -> SqliteRepository:
    instance = SqliteRepository(tmp_path / "resourceos.db")
    yield instance
    instance.close()


class FakeRunner:
    """A minimal `refresh.contracts.RefreshRunner` implementation for tests."""

    def __init__(self, *, outcome: str = "succeeded") -> None:
        self.outcome = outcome
        self.calls: list[RunReport] = []

    async def run(self, report: RunReport) -> RunReport:
        self.calls.append(report)
        if self.outcome == "raise":
            raise RuntimeError("boom")
        return report.model_copy(
            update={"status": self.outcome, "finished_at": datetime.now(tz=timezone.utc)}
        )


class FakeSync:
    """Same public shape as `storage.r2_sync.R2DataSync` (pull/push/aclose)."""

    def __init__(
        self, *, push_should_fail: bool = False, push_error: Exception | None = None
    ) -> None:
        self.pushed: list[tuple[Path, str]] = []
        self.push_should_fail = push_should_fail
        self.push_error = push_error

    async def pull(self, dest: Path) -> bool:
        return False

    async def push(self, src: Path, message: str) -> str:
        if self.push_should_fail:
            from storage.r2_sync import DataSyncError

            raise DataSyncError("push failed")
        if self.push_error is not None:
            raise self.push_error
        self.pushed.append((src, message))
        return "deadbeef"

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def fake_sync() -> FakeSync:
    return FakeSync()


def make_client(
    repository: SqliteRepository,
    seed_file: Path,
    *,
    password: str | None = RESOURCEOS_PASSWORD,
    sync=None,
    runner_factory=None,
) -> Generator[TestClient, None, None]:
    """Build a TestClient around a fully injected app: real repository +
    seed file, fake sync/runner so no network call ever happens in tests.
    """
    settings = Settings(
        password=password,
        cors_origins=["https://example.com"],
        db_path=str(repository._path),  # noqa: SLF001 - test-only introspection
        seed_path=str(seed_file),
    )
    app = create_app(
        settings=settings,
        repository=repository,
        sync=sync,
        runner_factory=runner_factory or (lambda repo: FakeRunner()),
    )
    # Every route but /api/health now requires X-ResourceOS-Key (see
    # api/deps.py::require_admin, wired in api/main.py::create_app). Sending
    # it as a client-level default header means existing tests keep working
    # unchanged; a test that specifically covers the missing/wrong key path
    # overrides this header per-request.
    default_headers = {"X-ResourceOS-Key": derive_api_key(password)} if password else {}
    with TestClient(app, headers=default_headers) as client:
        yield client


@pytest.fixture
def client(repository: SqliteRepository, seed_file: Path):
    yield from make_client(repository, seed_file)
