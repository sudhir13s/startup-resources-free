"""`GET /api/changes` — the reverse-chronological field-change feed."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.deps import get_repository
from domain.changes import FieldChange
from storage.repository import Repository

router = APIRouter(prefix="/api", tags=["changes"])


class ChangesResponse(BaseModel):
    total: int
    items: list[FieldChange]


@router.get("/changes", response_model=ChangesResponse)
async def get_changes(
    repository: Repository = Depends(get_repository),
    limit: int = Query(default=200, ge=1, le=1000),
    since: date | None = Query(default=None, description="YYYY-MM-DD lower bound"),
) -> ChangesResponse:
    items = repository.list_changes(limit=limit, since=since)
    return ChangesResponse(total=len(items), items=items)
