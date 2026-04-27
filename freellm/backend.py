"""Backend interface — single-provider call execution.

The router (`freellm/router.py`) owns the chain logic: filter providers
by env-var presence and quota state, then walk the chain trying each
one. The backend executes ONE provider call and returns a `Result`
(or raises). It does NOT loop. It does NOT track quotas.

Two implementations ship in `freellm/backends/`:

- `omniroute` — production. Calls an OmniRoute proxy via the
  OpenAI-compatible API at `localhost:20128/api/v1`. Lazy-imports
  the `omni_route_config` package + spins OmniRoute up on first
  call. Used by the daily pipeline + agents.
- `mock` — deterministic. No network. Used by tests + by callers
  who want a stable smoke result.

Selection: env var `FREELLM_BACKEND` ("omniroute" | "mock").
Default = "omniroute". Tests set FREELLM_BACKEND=mock.

Callers go through `get_backend()` (process-level singleton).
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from freellm.schemas import Result


@runtime_checkable
class Backend(Protocol):
    """Executes a single-provider call. Router does the chain."""

    name: str

    async def call_text_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
    ) -> Result: ...

    async def call_vision_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
    ) -> Result: ...

    async def call_embed_one(
        self,
        *,
        provider: str,
        model: str,
        inputs: list[str],
        timeout_s: int = 60,
    ) -> Result: ...

    async def aclose(self) -> None: ...


_singleton: Backend | None = None


def get_backend() -> Backend:
    """Return the process-level Backend, lazy-instantiated.

    First call decides the backend kind from `FREELLM_BACKEND`.
    Subsequent calls return the same instance — important for the
    OmniRoute backend, which caches the lifecycle (start, register,
    OpenAI client) across calls.
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    kind = os.environ.get("FREELLM_BACKEND", "omniroute").strip().lower()
    if kind == "mock":
        from freellm.backends.mock import MockBackend

        _singleton = MockBackend()
    elif kind == "omniroute":
        from freellm.backends.omniroute import OmniRouteBackend

        _singleton = OmniRouteBackend()
    else:
        raise ValueError(
            f"Unknown FREELLM_BACKEND={kind!r}. Use 'omniroute' or 'mock'."
        )
    return _singleton


def set_backend(backend: Backend | None) -> None:
    """Override the singleton. Used by tests + by callers that build
    their own backend (e.g. with a custom OmniRoute base_url).

    Pass None to clear so the next `get_backend()` rebuilds from env.
    """
    global _singleton
    _singleton = backend
