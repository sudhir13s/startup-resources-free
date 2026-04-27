"""freellm — free-LLM router library.

Curated catalog of free-tier LLM / multimodal providers, with quota-aware
fallback routing so total spend stays at $0. Reusable as a library outside
this project; designed to graduate to its own PyPI package later.

v0.2 status: text / vision / embed runtimes wired through OmniRoute.
image_gen / video_gen / stt / tts remain dry-run only — they land with
the Media Benchmark (v0.3+).

Public API:

    from freellm import (
        call_text, call_vision, call_embed,           # live in v0.2
        call_image_gen, call_video_gen, call_stt, call_tts,  # dry-run only
        Result, Plan, ProviderEntry,
        AllProvidersExhaustedError,
        Backend, get_backend, set_backend,
    )

See `.claude/rules/project/freellm-router.md` for the full spec.
"""

from __future__ import annotations

from freellm.backend import Backend, get_backend, set_backend
from freellm.providers import PROVIDERS, list_providers
from freellm.router import (
    AllProvidersExhaustedError,
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

__version__ = "0.2.0"

__all__ = [
    "PROVIDERS",
    "list_providers",
    "call_text",
    "call_vision",
    "call_image_gen",
    "call_video_gen",
    "call_embed",
    "call_stt",
    "call_tts",
    "plan",
    "AllProvidersExhaustedError",
    "Backend",
    "get_backend",
    "set_backend",
    "Modality",
    "Plan",
    "ProviderEntry",
    "Result",
    "__version__",
]
