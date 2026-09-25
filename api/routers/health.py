"""`GET /api/health` and the friendly `GET /` index."""

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


@router.get("/")
async def root() -> dict:
    """Friendly index at `/` so a direct visit shows the live service identity."""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "ok",
        "endpoints": {
            "health": "/api/health",
            "providers": "/api/providers",
            "openapi": "/openapi.json",
            "docs": "/docs",
        },
        "docs_url": "/docs",
        "github": "https://github.com/sudhir13s/startup-resources-free",
    }
