"""freellm — free-LLM router library.

Curated catalog of free-tier LLM / multimodal providers, with quota-aware
fallback routing (including automatic cooldown rotation on rate limits)
so total spend stays at $0. Reusable as a library outside this project;
designed to graduate to its own PyPI package later.

v0.3 status: text / vision / embed runtimes wired through a plain
OpenAI-compatible httpx backend (no sidecar, fits a 512 MB Render
instance). image_gen / video_gen / stt / tts remain dry-run only — they
land with the Media Benchmark (v0.3+).

Public API:

    from freellm import (
        call_text, call_vision, call_embed,           # live
        call_image_gen, call_video_gen, call_stt, call_tts,  # dry-run only
        Result, Plan, ProviderEntry,
        AllProvidersExhaustedError, RateLimitedError, TransientProviderError,
        AuthError, ProviderRequestError,
        Backend, get_backend, set_backend,
        configure,
    )

See `.claude/rules/project/freellm-router.md` for the full spec.
"""

from __future__ import annotations

from freellm import quotas
from freellm.backend import Backend, get_backend, set_backend
from freellm.errors import (
    AllProvidersExhaustedError,
    AuthError,
    ProviderRequestError,
    RateLimitedError,
    TransientProviderError,
)
from freellm.providers import PROVIDERS, list_providers
from freellm.quotas import MemoryStateStore, StateStore
from freellm.router import (
    call_embed,
    call_image_gen,
    call_stt,
    call_text,
    call_tts,
    call_video_gen,
    call_vision,
    plan,
)
from freellm.schemas import Modality, Plan, ProviderEntry, Result

__version__ = "0.3.0"


def configure(*, state_store: StateStore | None = None) -> None:
    """Inject a custom quota StateStore (e.g. the host app's SQLite
    repository). Called once at startup by the FastAPI service; tests
    and local scripts can rely on the default `JsonFileStateStore`.
    """
    quotas.configure(state_store=state_store)


__all__ = [
    "PROVIDERS",
    "AllProvidersExhaustedError",
    "AuthError",
    "Backend",
    "MemoryStateStore",
    "Modality",
    "Plan",
    "ProviderEntry",
    "ProviderRequestError",
    "RateLimitedError",
    "Result",
    "StateStore",
    "TransientProviderError",
    "__version__",
    "call_embed",
    "call_image_gen",
    "call_stt",
    "call_text",
    "call_tts",
    "call_video_gen",
    "call_vision",
    "configure",
    "get_backend",
    "list_providers",
    "plan",
    "quotas",
    "set_backend",
]
