"""`GET /api/health` — the only unauthenticated route (Render's health check).

The API is otherwise fully private (see `api.main.create_app`), so the old
friendly `GET /` index — which just pointed at `/docs` — is gone along with
`/docs`/`/redoc`/`/openapi.json`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

SERVICE_NAME = "ResourceOS API"
SERVICE_VERSION = "0.2.0"

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service_name: str
    version: str
    data_synced_at: str | None


@router.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service_name=SERVICE_NAME,
        version=SERVICE_VERSION,
        data_synced_at=request.app.state.data_synced_at,
    )
