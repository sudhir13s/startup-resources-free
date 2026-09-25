"""Backend interface — single-provider call execution.

The router (`freellm/router.py`) owns the chain logic: filter providers
by env-var presence and quota state, then walk the chain trying each
one. The backend executes ONE provider call and returns a `Result`
(or raises). It does NOT loop. It does NOT track quotas.

Two implementations ship in `freellm/backends/`:

- `openai_compat` — production. Plain async httpx against each
  provider's OpenAI-compatible endpoint (`base_url` + `api_key` come
  from the router, resolved from the catalog + env var). No sidecar
  process, no heavy SDK — fits a 512 MB Render free web service.
- `mock` — deterministic. No network. Used by tests + by callers
  who want a stable smoke result.

Selection: env var `FREELLM_BACKEND` ("openai_compat" | "mock").
Default = "openai_compat". Tests set FREELLM_BACKEND=mock.

Callers go through `get_backend()` (process-level singleton).
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from freellm.schemas import Result


@runtime_checkable
class Backend(Protocol):
    """Executes a single-provider call. Router does the chain.

    `api_key` / `base_url` are optional so `MockBackend` (no network) can
    ignore them while `OpenAICompatBackend` requires them — the router
    always passes both, resolved from the catalog entry + its env var.
    """

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
        api_key: str = "",
        base_url: str = "",
        response_format: dict[str, str] | None = None,
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
        api_key: str = "",
        base_url: str = "",
    ) -> Result: ...

    async def call_embed_one(
        self,
        *,
        provider: str,
        model: str,
        inputs: list[str],
        timeout_s: int = 60,
        api_key: str = "",
        base_url: str = "",
    ) -> Result: ...

    async def aclose(self) -> None: ...


_singleton: Backend | None = None


def get_backend() -> Backend:
    """Return the process-level Backend, lazy-instantiated.

    First call decides the backend kind from `FREELLM_BACKEND`.
    Subsequent calls return the same instance — important for the
    openai_compat backend, which reuses one httpx.AsyncClient.
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    kind = os.environ.get("FREELLM_BACKEND", "openai_compat").strip().lower()
    if kind == "mock":
        from freellm.backends.mock import MockBackend

        _singleton = MockBackend()
    elif kind == "openai_compat":
        from freellm.backends.openai_compat import OpenAICompatBackend

        _singleton = OpenAICompatBackend()
    else:
        raise ValueError(
            f"Unknown FREELLM_BACKEND={kind!r}. Use 'openai_compat' or 'mock'."
        )
    return _singleton


def set_backend(backend: Backend | None) -> None:
    """Override the singleton. Used by tests + by callers that build
    their own backend (e.g. with a custom base_url override).

    Pass None to clear so the next `get_backend()` rebuilds from env.
    """
    global _singleton
    _singleton = backend
