"""Refresh runs, discovery candidates, and the human verify queue."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from domain.records import ProviderRecord

RunStatus = Literal["running", "succeeded", "partial", "failed"]
RunTrigger = Literal["button", "cli", "test"]

OutcomeStatus = Literal[
    "unchanged",       # page hash same, or extraction produced no content change
    "updated",         # new version stored
    "new",             # first version stored
    "queued-verify",   # low confidence → waiting for a human
    "skipped",         # robots.txt / blocklist / budget exhausted
    "failed",          # fetch or extraction error
]

CandidateStatus = Literal["pending", "approved", "rejected", "imported"]
VerifyStatus = Literal["pending", "accepted", "rejected", "expired"]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class RefreshOptions(BaseModel):
    """What the Refresh button (or CLI) asks for."""

    provider_ids: list[str] | None = None   # None = every stored provider
    discover: bool = False                  # also search for new providers
    force: bool = False                     # ignore the page-hash gate
    max_llm_calls: int = Field(default=200, ge=1, le=2000)


class ProviderOutcome(BaseModel):
    """What happened to one provider during a run — one row in the run log."""

    provider_id: str
    status: OutcomeStatus
    message: str = ""                    # human-readable reason, never empty on failure
    source_url: str | None = None
    llm_provider: str | None = None      # e.g. "groq/llama-3.3-70b-versatile"
    changes: int = 0
    duration_ms: int = 0


class RunReport(BaseModel):
    """A refresh run, persisted and shown on the Runs page."""

    run_id: str
    trigger: RunTrigger
    options: RefreshOptions
    status: RunStatus = "running"
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    outcomes: list[ProviderOutcome] = Field(default_factory=list)
    candidates_found: int = 0
    llm_calls: int = 0
    search_calls: int = 0
    data_pushed: bool = False            # DB committed to the `data` branch
    errors: list[str] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for outcome in self.outcomes:
            totals[outcome.status] = totals.get(outcome.status, 0) + 1
        return totals


class Candidate(BaseModel):
    """A possibly-new provider found by discovery, waiting for Approve/Reject."""

    candidate_id: str                    # sha1 of normalized URL
    url: str
    domain: str
    title: str
    snippet: str = ""
    category_guess: str | None = None
    reason: str = ""                     # why the ranker thinks it is a free offer
    score: float = 0.0
    found_via: str = ""                  # "tavily", "aggregator:grants.startupspeedrun.org"
    status: CandidateStatus = "pending"
    created_at: datetime = Field(default_factory=_now)


class VerifyItem(BaseModel):
    """A low-confidence extraction held back from the catalog until a human decides."""

    item_id: str
    provider_id: str
    proposed: ProviderRecord
    reason: str
    run_id: str | None = None
    status: VerifyStatus = "pending"
    created_at: datetime = Field(default_factory=_now)
