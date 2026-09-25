"""Shared FastAPI dependencies: repository access + the API-key guard."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request

from api.auth import derive_api_key
from storage.repository import Repository


def get_repository(request: Request) -> Repository:
    """The single shared `Repository` instance, opened once at startup."""
    return request.app.state.repository


def require_admin(
    request: Request,
    x_resourceos_key: str | None = Header(default=None),
) -> None:
    """Guard applied to every route except `GET /api/health`: compares the
    `X-ResourceOS-Key` header (constant-time) against the key derived from
    `RESOURCEOS_PASSWORD`.

    503 when the deployment has no `RESOURCEOS_PASSWORD` configured (the API
    is simply unavailable rather than silently open); 401 on any mismatch,
    including a missing header. The whole API is private — the browser never
    calls it directly, only the Next.js server routes, which derive the same
    key and send it on every request. The raw password itself is never sent
    over the wire and never logged.
    """
    password = request.app.state.settings.password
    if not password:
        raise HTTPException(status_code=503, detail="API is not configured")

    expected = derive_api_key(password.get_secret_value())
    if not x_resourceos_key or not hmac.compare_digest(x_resourceos_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing key")
