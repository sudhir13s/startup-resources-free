"""Shared FastAPI dependencies: repository access + the admin-token guard."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request

from storage.repository import Repository


def get_repository(request: Request) -> Repository:
    """The single shared `Repository` instance, opened once at startup."""
    return request.app.state.repository


def require_admin(
    request: Request, x_admin_token: str | None = Header(default=None)
) -> None:
    """Guard for write endpoints: compares `X-Admin-Token` via constant-time compare.

    503 when the deployment has no `ADMIN_TOKEN` configured (refresh is
    simply unavailable rather than silently open); 401 on any mismatch,
    including a missing header.
    """
    admin_token: str | None = request.app.state.settings.admin_token
    if not admin_token:
        raise HTTPException(status_code=503, detail="Refresh is not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
