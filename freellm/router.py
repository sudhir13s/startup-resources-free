"""Quota-aware fallback chain executor.

Public API:
- `plan(modality, task_name)` — pure preview, no network.
- `call_text/_vision/_image_gen/_video_gen/_embed/_stt/_tts(...)` — async,
  walk the chain, hit the backend for each candidate, record quota state.
- `dry_run=True` on any call_* returns the same Plan as `plan()`.

Chain semantics (per `agentic-pipeline.md`):
- Try each candidate in `plan().options` order.
- On success: record_success in quotas, return Result with
  `chain_attempted` populated.
- On failure: record_failure in quotas, move to next candidate.
- All exhausted: raise `AllProvidersExhaustedError(chain_attempted)`.

The router NEVER imports an LLM SDK directly — it delegates to the
`Backend` resolved by `freellm.backend.get_backend()`. Swapping
backends (mock for tests, OmniRoute in prod, future LiteLLM-direct)
needs zero changes here.

`call_image_gen / call_video_gen / call_stt / call_tts` are scoped out
of B1: the agents and dashboard surfaces shipping next don't need them.
They raise `NotImplementedError` with a pointer to the v0.3 work.
"""

from __future__ import annotations

import os
from typing import Any

from freellm import quotas
from freellm.backend import Backend, get_backend
from freellm.providers import PROVIDERS, list_providers
from freellm.schemas import (
    Modality,
    Plan,
    PlanOption,
    ProviderEntry,
    Result,
)


class AllProvidersExhaustedError(RuntimeError):
    """Raised when every provider in the chain has been tried + failed."""

    def __init__(self, chain_attempted: list[str]):
        self.chain_attempted = chain_attempted
        super().__init__(
            f"All free providers exhausted. Attempted: {', '.join(chain_attempted)}"
        )


def _filter_chain(
    entries: list[ProviderEntry], state: quotas.QuotaState, allow_paid: bool
) -> tuple[list[tuple[ProviderEntry, PlanOption]], dict[str, str]]:
    """Apply env-var + disable + quota filters. Returns (kept, reason_skipped)."""
    kept: list[tuple[ProviderEntry, PlanOption]] = []
    skipped: dict[str, str] = {}
    for e in entries:
        key = f"{e.provider}/{e.model}"
        if not allow_paid and not os.environ.get(e.env_var):
            skipped[key] = f"missing env var {e.env_var}"
            continue
        usage = quotas.get(state, e.provider, e.model)
        if quotas.is_disabled(usage):
            skipped[key] = f"disabled until {usage.disabled_until}"
            continue
        opt = PlanOption(
            provider=e.provider,
            model=e.model,
            env_var_present=bool(os.environ.get(e.env_var)),
            quota_remaining=quotas.remaining_hint(usage),
            speed_tier=e.speed_tier,
            free_tier_kind=e.free_tier.kind,  # type: ignore[union-attr]
        )
        kept.append((e, opt))
    return kept, skipped


def plan(
    *,
    modality: Modality,
    task_name: str,
    allow_paid: bool | None = None,
) -> Plan:
    """Compute the route a call would take WITHOUT making the call.

    Used by the dashboard's "Test the chain" button + the `python -m
    freellm plan` CLI subcommand. No network, no backend.
    """
    if allow_paid is None:
        allow_paid = os.environ.get("LLM_ALLOW_PAID") == "1"
    entries = PROVIDERS.get(modality, [])
    state = quotas.load()
    kept, skipped = _filter_chain(entries, state, allow_paid=allow_paid)
    options = [opt for _, opt in kept]
    chosen = options[0] if options else None
    return Plan(
        modality=modality,
        task_name=task_name,
        options=options,
        chosen=chosen,
        reason_skipped=skipped,
    )


# ============================================================
# Chain executor — shared by every modality.
# ============================================================


async def _execute_chain(
    *,
    modality: Modality,
    task_name: str,
    one_call: Any,  # bound method on Backend
    allow_paid: bool | None,
    persist_quotas: bool,
) -> Result:
    """Run plan() then walk options against `one_call`.

    `one_call(*, provider, model)` -> Result. Caller closes over its
    modality-specific kwargs (messages, inputs, etc.).
    """
    p = plan(modality=modality, task_name=task_name, allow_paid=allow_paid)
    if not p.options:
        raise AllProvidersExhaustedError([])

    state = quotas.load()
    chain_attempted: list[str] = []
    last_error: BaseException | None = None
    try:
        for opt in p.options:
            tag = f"{opt.provider}/{opt.model}"
            chain_attempted.append(tag)
            try:
                result = await one_call(provider=opt.provider, model=opt.model)
                quotas.record_success(
                    state,
                    provider=opt.provider,
                    model=opt.model,
                    tokens_in=result.tokens_in or 0,
                    tokens_out=result.tokens_out or 0,
                )
                result.chain_attempted = chain_attempted
                return result
            except Exception as e:
                last_error = e
                quotas.record_failure(
                    state,
                    provider=opt.provider,
                    model=opt.model,
                    reason=f"{type(e).__name__}: {e}"[:200],
                )
                continue
    finally:
        if persist_quotas:
            quotas.save(state)

    err = AllProvidersExhaustedError(chain_attempted)
    if last_error is not None:
        raise err from last_error
    raise err


# ============================================================
# Modality-specific call_* entry points.
# ============================================================


def _resolve_backend(backend: Backend | None) -> Backend:
    return backend if backend is not None else get_backend()


async def call_text(
    *,
    messages: list[dict[str, Any]],
    task_name: str,
    model_chain: list[str] | None = None,
    response_model: type | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.0,
    timeout_s: int = 60,
    dry_run: bool = False,
    backend: Backend | None = None,
    allow_paid: bool | None = None,
    persist_quotas: bool = True,
) -> Result | Plan:
    if dry_run:
        return plan(modality="text", task_name=task_name, allow_paid=allow_paid)
    _ = (model_chain, response_model)  # B2 will use response_model for structured output
    be = _resolve_backend(backend)

    async def one(*, provider: str, model: str) -> Result:
        return await be.call_text_one(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    return await _execute_chain(
        modality="text",
        task_name=task_name,
        one_call=one,
        allow_paid=allow_paid,
        persist_quotas=persist_quotas,
    )


async def call_vision(
    *,
    messages: list[dict[str, Any]],
    image_bytes: bytes | None = None,
    task_name: str,
    max_tokens: int = 2000,
    temperature: float = 0.0,
    timeout_s: int = 60,
    dry_run: bool = False,
    backend: Backend | None = None,
    allow_paid: bool | None = None,
    persist_quotas: bool = True,
) -> Result | Plan:
    if dry_run:
        return plan(modality="vision", task_name=task_name, allow_paid=allow_paid)
    _ = image_bytes  # caller embeds image_url parts in `messages`; reserved for B6
    be = _resolve_backend(backend)

    async def one(*, provider: str, model: str) -> Result:
        return await be.call_vision_one(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    return await _execute_chain(
        modality="vision",
        task_name=task_name,
        one_call=one,
        allow_paid=allow_paid,
        persist_quotas=persist_quotas,
    )


async def call_embed(
    *,
    inputs: list[str],
    task_name: str,
    timeout_s: int = 60,
    dry_run: bool = False,
    backend: Backend | None = None,
    allow_paid: bool | None = None,
    persist_quotas: bool = True,
) -> Result | Plan:
    if dry_run:
        return plan(modality="embed", task_name=task_name, allow_paid=allow_paid)
    be = _resolve_backend(backend)

    async def one(*, provider: str, model: str) -> Result:
        return await be.call_embed_one(
            provider=provider,
            model=model,
            inputs=inputs,
            timeout_s=timeout_s,
        )

    return await _execute_chain(
        modality="embed",
        task_name=task_name,
        one_call=one,
        allow_paid=allow_paid,
        persist_quotas=persist_quotas,
    )


# ============================================================
# Scoped out of B1 — agents/pipeline don't need these yet.
# Land with B6/B7/B8 (Media Benchmark v0.3+).
# ============================================================


async def call_image_gen(
    *,
    prompt: str,
    task_name: str,
    width: int = 1024,
    height: int = 1024,
    dry_run: bool = False,
) -> Result | Plan:
    if dry_run:
        return plan(modality="image_gen", task_name=task_name)
    _ = (prompt, width, height)
    raise NotImplementedError(
        "call_image_gen runtime is v0.3 (Media Benchmark) work. "
        "Use dry_run=True for plan preview."
    )


async def call_video_gen(
    *,
    prompt: str,
    task_name: str,
    duration_s: float = 4.0,
    resolution: str = "720p",
    dry_run: bool = False,
) -> Result | Plan:
    if dry_run:
        return plan(modality="video_gen", task_name=task_name)
    _ = (prompt, duration_s, resolution)
    raise NotImplementedError(
        "call_video_gen runtime is v0.3 (Media Benchmark) work."
    )


async def call_stt(
    *,
    audio_bytes: bytes,
    task_name: str,
    language: str | None = None,
    dry_run: bool = False,
) -> Result | Plan:
    if dry_run:
        return plan(modality="stt", task_name=task_name)
    _ = (audio_bytes, language)
    raise NotImplementedError("call_stt runtime is v0.3 work.")


async def call_tts(
    *,
    text: str,
    task_name: str,
    voice: str | None = None,
    dry_run: bool = False,
) -> Result | Plan:
    if dry_run:
        return plan(modality="tts", task_name=task_name)
    _ = (text, voice)
    raise NotImplementedError("call_tts runtime is v0.3 work.")


# ============================================================
# Catalog inspection helpers — unchanged from v0.1.
# ============================================================


def catalog_summary() -> dict[str, int]:
    return {modality: len(entries) for modality, entries in PROVIDERS.items()}


def total_entries() -> int:
    return sum(len(e) for e in PROVIDERS.values())


def list_all() -> list[ProviderEntry]:
    return list_providers()
