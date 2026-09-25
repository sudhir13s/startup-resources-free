"""Repository contract — the only way the rest of the app reads or writes data.

`storage/sqlite_repository.py` implements it. Tests may use the same SQLite
implementation against a temp file; nothing mocks this interface.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from domain.changes import FieldChange
from domain.records import ProviderRecord
from domain.runs import Candidate, CandidateStatus, RunReport, VerifyItem, VerifyStatus


class StoredVersion(BaseModel):
    """One stored version of an offer (history is append-only)."""

    provider_id: str
    version: int
    record: ProviderRecord
    source: str              # "seed", "refresh", "verify", "candidate"
    run_id: str | None
    created_at: datetime


class SaveResult(BaseModel):
    """Outcome of `save_provider`."""

    stored: bool             # False when the content fingerprint was unchanged
    version: int             # the current version after the call
    changes: list[FieldChange]


class Repository(Protocol):
    # --- Catalog ---
    def list_providers(self) -> list[ProviderRecord]:
        """Latest version of every provider whose status is not deleted."""
        ...

    def get_provider(self, provider_id: str) -> ProviderRecord | None: ...

    def history(self, provider_id: str, limit: int = 20) -> list[StoredVersion]: ...

    def save_provider(
        self, record: ProviderRecord, *, source: str, run_id: str | None = None
    ) -> SaveResult:
        """Append a new version only if the content fingerprint changed.

        Always records freshness (last_verified_at / scraped_at) on the
        current version, even when no new version is stored. Diffs against
        the previous version and persists the resulting FieldChanges.
        """
        ...

    # --- Changes feed ---
    def list_changes(self, *, limit: int = 200, since: date | None = None) -> list[FieldChange]: ...

    # --- Runs ---
    def create_run(self, report: RunReport) -> None:
        """Insert a run. Raises RunAlreadyActiveError if another run is `running`."""
        ...

    def update_run(self, report: RunReport) -> None: ...

    def get_run(self, run_id: str) -> RunReport | None: ...

    def list_runs(self, limit: int = 20) -> list[RunReport]: ...

    def active_run(self) -> RunReport | None: ...

    # --- Discovery candidates ---
    def add_candidates(self, candidates: list[Candidate]) -> int:
        """Insert new candidates; existing candidate_ids are ignored. Returns count inserted."""
        ...

    def list_candidates(self, status: CandidateStatus | None = "pending") -> list[Candidate]: ...

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> None: ...

    # --- Verify queue ---
    def enqueue_verify(self, item: VerifyItem) -> None: ...

    def list_verify(self, status: VerifyStatus | None = "pending") -> list[VerifyItem]: ...

    def set_verify_status(self, item_id: str, status: VerifyStatus) -> None: ...

    # --- Page-hash gate (skip the LLM when a page did not change) ---
    def get_page_hash(self, url: str) -> str | None: ...

    def set_page_hash(self, url: str, content_hash: str) -> None: ...

    # --- Small JSON state blobs (quota counters for freellm / search chain) ---
    def get_state(self, namespace: str) -> dict[str, Any]: ...

    def put_state(self, namespace: str, data: dict[str, Any]) -> None: ...


class RunAlreadyActiveError(RuntimeError):
    """Raised by `create_run` when a run is still marked `running`."""
