"""`GET /api/candidates` and the admin approve/reject actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_repository, require_admin
from domain.runs import Candidate, CandidateStatus
from storage.repository import Repository

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("", response_model=list[Candidate])
async def get_candidates(
    repository: Repository = Depends(get_repository),
    status: CandidateStatus | None = Query(default="pending"),
) -> list[Candidate]:
    return repository.list_candidates(status=status)


@router.post(
    "/{candidate_id}/approve", response_model=Candidate, dependencies=[Depends(require_admin)]
)
async def approve_candidate(
    candidate_id: str, repository: Repository = Depends(get_repository)
) -> Candidate:
    return _set_status(repository, candidate_id, "approved")


@router.post(
    "/{candidate_id}/reject", response_model=Candidate, dependencies=[Depends(require_admin)]
)
async def reject_candidate(
    candidate_id: str, repository: Repository = Depends(get_repository)
) -> Candidate:
    return _set_status(repository, candidate_id, "rejected")


def _set_status(repository: Repository, candidate_id: str, status: CandidateStatus) -> Candidate:
    """Shared approve/reject body: look up, guard 404, persist, return the updated row."""
    existing = _find(repository, candidate_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate_id: {candidate_id!r}")
    repository.set_candidate_status(candidate_id, status)
    updated = _find(repository, candidate_id, status=status)
    assert updated is not None  # just written above
    return updated


def _find(
    repository: Repository, candidate_id: str, *, status: CandidateStatus | None = None
) -> Candidate | None:
    for candidate in repository.list_candidates(status=status):
        if candidate.candidate_id == candidate_id:
            return candidate
    # The target status bucket didn't have it (e.g. searching "approved" for
    # a still-pending row) — fall back to an unfiltered scan.
    if status is not None:
        for candidate in repository.list_candidates(status=None):
            if candidate.candidate_id == candidate_id:
                return candidate
    return None
