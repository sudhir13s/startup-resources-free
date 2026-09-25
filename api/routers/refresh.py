"""`GET /api/refresh/status` and `POST /api/refresh` [admin]."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.deps import get_repository, require_admin
from api.services.refresh_service import execute_and_sync, start_run
from domain.runs import RefreshOptions, RunReport
from storage.repository import Repository, RunAlreadyActiveError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


class RefreshStatusResponse(BaseModel):
    active: RunReport | None
    last: RunReport | None
    data_synced_at: str | None


class RefreshAcceptedResponse(BaseModel):
    run_id: str


@router.get("/status", response_model=RefreshStatusResponse)
async def get_refresh_status(
    request: Request, repository: Repository = Depends(get_repository)
) -> RefreshStatusResponse:
    last_runs = repository.list_runs(limit=1)
    return RefreshStatusResponse(
        active=repository.active_run(),
        last=last_runs[0] if last_runs else None,
        data_synced_at=request.app.state.data_synced_at,
    )


@router.post(
    "",
    response_model=RefreshAcceptedResponse,
    status_code=202,
    dependencies=[Depends(require_admin)],
)
async def post_refresh(
    request: Request,
    options: RefreshOptions,
    repository: Repository = Depends(get_repository),
) -> RefreshAcceptedResponse:
    try:
        report = start_run(repository, options)
    except RunAlreadyActiveError as exc:
        raise HTTPException(status_code=409, detail="A refresh is already running") from exc

    task = asyncio.create_task(_run_in_background(request, repository, report))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
    return RefreshAcceptedResponse(run_id=report.run_id)


async def _run_in_background(request: Request, repository: Repository, report: RunReport) -> None:
    """Execute the run and, on success, push the DB — then update `data_synced_at`."""
    state = request.app.state

    def on_synced(synced_at) -> None:  # noqa: ANN001 - datetime, avoids importing just for the hint
        state.data_synced_at = synced_at.isoformat()

    await execute_and_sync(
        repository=repository,
        report=report,
        runner_factory=state.runner_factory,
        sync=state.sync,
        db_path=Path(state.settings.db_path),
        on_synced=on_synced,
    )
