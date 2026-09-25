"""`GET /api/runs` and `GET /api/runs/{run_id}`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_repository
from domain.runs import RunReport
from storage.repository import Repository

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs", response_model=list[RunReport])
async def get_runs(
    repository: Repository = Depends(get_repository),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[RunReport]:
    return repository.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=RunReport)
async def get_run(run_id: str, repository: Repository = Depends(get_repository)) -> RunReport:
    report = repository.get_run(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"unknown run_id: {run_id!r}")
    return report
