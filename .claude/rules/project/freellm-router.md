# Project Rule: `freellm/` — The Free-LLM Router Library

> Spec for the in-repo Python sub-package that knows every free-tier LLM / multimodal provider, tracks quotas, and routes calls in a chain so total spend stays at $0. Reusable as a library outside this project. Designed to graduate to its own PyPI package later.

## Why this exists as a separate package

Two reasons:

1. **The free-LLM catalog is volatile.** Providers add/remove free tiers monthly. Centralizing this knowledge lets every part of the project (`refresh/extract.py`, discovery, the API's freellm router) call one function and get the right provider auto-routed.
2. **Reusability beyond this project.** The router is useful for ANY hobby project that wants $0 LLM spend. Keeping it self-contained (no imports from `refresh/`, `api/`, or `storage/` — only an injected `StateStore` protocol) means you can `pip install freellm` from the standalone package later.

## Package layout

```
freellm/
  __init__.py           # public API surface — see below
  providers.py          # canonical catalog: who offers what for free, with limits
  backend.py            # the ONE OpenAI-compatible httpx backend every call_* goes through (no LiteLLM/sidecar)
  router.py             # quota-aware chain executor: call_text/call_vision/call_embed (live), call_image_gen/call_video_gen/call_stt/call_tts (dry-run), plan()
  quotas.py             # StateStore protocol + MemoryStateStore; cooldown-rotation state
  schemas.py            # Pydantic models: Modality, ProviderEntry, FreeTier variants, Result, Plan
  errors.py             # AllProvidersExhaustedError, RateLimitedError, TransientProviderError, AuthError, ProviderRequestError
  cli.py                # `python -m freellm` script entry
  __main__.py
  tests/
```

## Public API (LOCKED contract — `freellm/__init__.py`)

```python
from freellm import (
    call_text, call_vision, call_embed,                    # async, LIVE
    call_image_gen, call_video_gen, call_stt, call_tts,     # async, DRY-RUN ONLY (v0.3 status)
    Result, Plan, ProviderEntry,
    AllProvidersExhaustedError, RateLimitedError, TransientProviderError,
    AuthError, ProviderRequestError,
    Backend, get_backend, set_backend,
    configure,                                              # inject a StateStore at startup
)
```

Every `call_*` function:
- Is `async`.
- Takes a `task_name: str` (REQUIRED — for logs + per-task quota tracking).
- Takes the modality-specific input (`messages` for text/vision, etc.).
- Returns a `Result` with: `content`, `provider_used`, `model_used`, `latency_ms`, `cost_usd` (must be `0.0`), `tokens_in`, `tokens_out`, `chain_attempted` (providers tried before success).
- Raises `AllProvidersExhaustedError` if the chain runs out.

`plan(modality, task_name)` (also exported) returns a `Plan` — the ordered provider options
that would be tried, each one's quota/cooldown state, and the `chosen` option — without making
any actual call. This backs the CLI's `plan` subcommand and the dashboard's "Test the chain" UX.

`image_gen` / `video_gen` / `stt` / `tts` are dry-run-only in v0.3: `plan()` works for them, but
the live call path lands with the Media Benchmark (v0.3+, see `media-benchmark.md`).

## Catalog contract (`providers.py`)

The catalog is the source of truth. Structure:

```python
PROVIDERS: dict[Modality, list[ProviderEntry]] = {
    "text":      [...],
    "vision":    [...],
    "image_gen": [...],
    "video_gen": [...],
    "embed":     [...],
    "stt":       [...],
    "tts":       [...],
}

class ProviderEntry(BaseModel):
    provider: str               # provider slug (e.g. "groq", "gemini", "openrouter")
    model: str                  # provider-native model id (e.g. "llama-3.3-70b-versatile")
    free_tier: FreeTier         # quota describing what's free
    env_var: str                # API key env var (e.g. "GROQ_API_KEY")
    base_url: str               # OpenAI-compatible chat-completions base URL for this provider
    speed_tier: str             # "fast" | "medium" | "slow" — for ordering when quality is comparable
    last_verified: date         # human or smoke-test confirmed on this date
    geo_restrictions: list[str] # ISO codes if the provider isn't globally available
    notes: str | None
    docs_url: str | None
```

`FreeTier` is a discriminated union covering different quota shapes:
- `RpmRpd` (requests-per-minute + per-day cap)
- `TokensPerMonth`
- `RequestsPerDay`
- `OneTimeCredits` (e.g. "$5 free credits, never resets")
- `AlwaysFreeWithLimits` (e.g. HF Inference: free with rate caps but no expiry)

The catalog is human-curated. Discovery (`refresh/discover.py`) can SUGGEST new providers as
review candidates, but every `freellm/providers.py` catalog change requires a human-reviewed
PR. NEVER auto-merge.

## Routing strategy (`router.py`)

For each call:

1. Pull all `ProviderEntry` for the modality.
2. Filter out entries where the env var is missing.
3. Filter out entries in cooldown (set after a rate-limit response — `RateLimitedError` —
   until the cooldown window elapses).
4. Filter out entries that have hit their tracked quota cap in `quotas.py`.
5. Sort by catalog-declared priority and `speed_tier` (fast first when the caller didn't override).
6. Try each in order. On an auth failure (`AuthError`) or a non-retryable request error
   (`ProviderRequestError`): mark the provider failed for this call, move on. On
   `RateLimitedError` / `TransientProviderError`: respect `Retry-After` if present, start a
   cooldown, then move on.
7. On full chain exhaustion: raise `AllProvidersExhaustedError(chain_attempted)`.

The router never retries the same provider twice within one call — falling through to the next
provider in the chain IS the retry strategy.

## Quotas (`quotas.py`)

Per-provider quota and cooldown state is read/written through the `StateStore` protocol
(`get_state(namespace) -> dict`, `put_state(namespace, data) -> None`), namespaced as
`"freellm"`. Two implementations ship in the package:

- `JsonFileStateStore` (default) — writes to `${FREELLM_QUOTA_DIR}/quotas.json`, or
  `data/freellm/quotas.json` relative to cwd when unset. Used for local scripts and the CLI.
- `MemoryStateStore` — in-process dict, no disk I/O. Used in tests.

In production the FastAPI service calls `freellm.configure(state_store=<SqliteRepository>)`
once at startup (`api/main.py`'s lifespan), so quota state is persisted in the same SQLite
database that gets pushed to the `data` git branch — `freellm/` never imports `storage/`
directly; it only depends on the structural `StateStore` protocol.

Reset rules:
- Daily quotas reset at the provider's documented reset time (most reset at 00:00 UTC; some at
  midnight Pacific).
- One-time credits: never reset. When exhausted, the provider is excluded from further chain
  attempts until quota state is manually cleared.

The counter increments on every call attempt — including failed ones — because some providers
count failures against quota.

## Multimodal coverage (LOCKED list — verify monthly, providers move fast)

Initial catalog targets:

### Text
- groq/llama-3.3-70b-versatile (high RPM, daily cap)
- groq/llama-3.1-8b-instant
- cerebras/llama3.1-70b
- gemini/gemini-2.0-flash-exp + gemini-1.5-flash (generous free RPD)
- openrouter/* :free models (Llama 3 70B, Gemini Flash, Mistral, Qwen)
- together_ai/* free models
- mistral/* free tier
- huggingface/* (free HF Inference API)

### Vision
- gemini/gemini-1.5-flash (vision-capable)
- groq/llama-3.2-90b-vision
- openrouter/* :free vision models
- together_ai/* free vision models

### Image generation
- huggingface/black-forest-labs/FLUX.1-schnell (free HF Inference)
- huggingface/stabilityai/stable-diffusion-xl-base-1.0
- replicate/* free monthly quota
- fal_ai/* free quota
- together_ai/black-forest-labs/FLUX.1-schnell-Free

### Video generation
- replicate/* (limited free)
- fal_ai/* (limited free)
- huggingface/* (very slow; last resort)

### Embeddings
- voyage/voyage-3-lite (free tier)
- cohere/embed-english-v3.0 (free trial key)
- mistral/mistral-embed (free)
- gemini/text-embedding-004 (free RPD)
- huggingface/sentence-transformers/* (free HF Inference)

### Speech-to-text
- groq/whisper-large-v3 (very fast, free tier)
- huggingface/openai/whisper-* (free HF Inference)
- gemini/gemini-1.5-flash (audio input supported)

### Text-to-speech
- huggingface/* TTS models (free HF Inference)
- elevenlabs/* (free monthly quota — limited)
- fal_ai/* TTS (free)

Every entry MUST be backed by the provider's official free-tier doc. Anyone editing the catalog includes a docs URL + last-verified date in the PR description.

## CLI usage (`python -m freellm`, backed by `freellm/cli.py`)

```bash
# Show the catalog summary (counts per modality)
python -m freellm catalog

# Show the catalog for one modality
python -m freellm catalog --modality text

# Show the routing plan for a request without making the call
python -m freellm plan --modality text --task-name extract-record

# Show which provider env vars are set (never leaks values)
python -m freellm keys

# Send a 1-token request through the live text chain (skips cleanly with no keys set)
python -m freellm smoke --modality text

# Show persisted quota counters (JsonFileStateStore)
python -m freellm quotas

# Show the installed freellm version
python -m freellm version
```

## Never do (anti-patterns)

- Call a provider through anything other than `freellm/backend.py`'s OpenAI-compatible client —
  no direct provider SDK, no bespoke `httpx` call to an LLM endpoint elsewhere in the codebase.
- Add a paid model to the free chain without `LLM_ALLOW_PAID=1` opt-in.
- Read API keys from anything except env vars.
- Persist chat history outside the caller's request — the router is stateless.
- Couple `freellm/` to project-specific code (`refresh/`, `api/`, `storage/`). One-way: those
  import freellm and inject a `StateStore`; freellm imports nothing project-local.
- Retry the same provider in a tight loop — falling through to the next provider IS the retry.
- Silently cap costs (raise instead — silent caps cause weird bugs).

## Why not LiteLLM?

Architecture v2 (2026-09-25) replaced an earlier LiteLLM-based design with a plain
OpenAI-compatible `httpx` backend, specifically because Render's free instance caps at 512 MB —
LiteLLM plus its transitive dependencies didn't reliably fit alongside FastAPI, Pydantic, and
the rest of the API process. What `freellm/` still provides over calling providers raw:
- Curated free-tier catalog with usage metadata (so we KNOW which models are free without trial-and-error).
- Persisted per-provider quota + cooldown tracking, injected via the host app's own storage.
- Modality-aware routing (different chains per modality, not one chain that mixes them).
- A CLI for inspecting / testing the chain, and a `plan()` dry-run mode for the dashboard's
  "Test the chain" UX.
- A single, small, audited HTTP surface (`freellm/backend.py`) rather than a heavy dependency.

LiteLLM remains fine for local experimentation outside the API process; it is not linked into
anything that runs on Render.
