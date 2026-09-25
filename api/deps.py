"""Shared FastAPI dependencies: repository access + the passphrase guard."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request

from storage.repository import Repository


def get_repository(request: Request) -> Repository:
    """The single shared `Repository` instance, opened once at startup."""
    return request.app.state.repository


def require_admin(
    request: Request,
    x_resourceos_passphrase: str | None = Header(default=None),
) -> None:
    """Guard for write endpoints: compares `X-ResourceOS-Passphrase` via constant-time compare.

    503 when the deployment has no `RESOURCEOS_PASSPHRASE` configured (refresh is
    simply unavailable rather than silently open); 401 on any mismatch,
    including a missing header.
    """
    passphrase: str | None = request.app.state.settings.passphrase
    if not passphrase:
        raise HTTPException(status_code=503, detail="Refresh is not configured")
    supplied = x_resourceos_passphrase
    if not supplied or not hmac.compare_digest(supplied, passphrase):
        raise HTTPException(status_code=401, detail="Invalid or missing passphrase")
