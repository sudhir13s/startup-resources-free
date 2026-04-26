# Project Rule: `freellm/` — The Free-LLM Router Library

> Spec for the in-repo Python sub-package that knows every free-tier LLM / multimodal provider, tracks quotas, and routes calls in a chain so total spend stays at $0. Reusable as a library outside this project. Designed to graduate to its own PyPI package later.

## Why this exists as a separate package

Two reasons:

1. **The free-LLM catalog is volatile.** Providers add/remove free tiers monthly. Centralizing this knowledge lets every part of the project (research agent, extractor, tier classifier) call one function and get the right provider auto-routed.
2. **Reusability beyond this project.** The router is useful for ANY hobby project that wants $0 LLM spend. Keeping it self-contained (no imports from `agents/` or `pipeline/`) means you can `pip install freellm` from the standalone package later.

## Package layout

```
freellm/
  __init__.py           # public API (call_text, call_vision, call_image_gen, call_embed, call_video_gen, call_stt, call_tts)
  providers.py          # canonical catalog: who offers what for free, with limits
  router.py             # quota-aware chain executor + LiteLLM wrapper
  quotas.py             # persisted per-provider per-day counters
  schemas.py            # Pydantic request/response models per modality
  cli.py                # `python -m freellm` script entry
  prompts/              # default system prompts the router uses for self-checks
  tests/
```

## Public API (LOCKED contract)

```python
from freellm import (
    call_text,        # async — chat / completion
    call_vision,      # async — text + image input → text output
    call_image_gen,   # async — text → image
    call_video_gen,   # async — text → short video clip
    call_embed,       # async — text → embedding vector
    call_stt,         # async — audio → text
    call_tts,         # async — text → audio
    Result,           # Pydantic result type carrying provider_used, latency, cost
    Plan,             # describes the chosen chain before execution (dry-run mode)
)
```

Every function:
- Is `async`.
- Takes a `task_name: str` (REQUIRED — for logs + per-task quota tracking).
- Takes the modality-specific input (messages / image_bytes / prompt / audio_bytes).
- Returns a `Result` with: `content`, `provider_used`, `model_used`, `latency_ms`, `cost_usd` (must be `0.0`), `tokens_in`, `tokens_out`, `chain_attempted` (list of providers tried before success).
- Raises `AllProvidersExhaustedError` if the chain runs out.

Every function ALSO supports a `dry_run=True` flag returning a `Plan` object showing which provider would be picked first, second, … without making any actual call. Useful for the dashboard's "Test the chain" button.

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
    provider: str               # litellm provider slug (e.g. "groq", "openrouter", "fal_ai")
    model: str                  # litellm model id (e.g. "llama-3.3-70b-versatile")
    free_tier: FreeTier         # quota describing what's free
    env_var: str                # API key env var (e.g. "GROQ_API_KEY")
    speed_tier: str             # "fast" | "medium" | "slow" — for ordering when quality is comparable
    last_verified: date         # human or smoke-test confirmed on this date
    geo_restrictions: list[str] # ISO codes if the provider isn't globally available
    notes: str | None
```

`FreeTier` is a discriminated union covering different quota shapes:
- `RpmRpd` (requests-per-minute + per-day cap)
- `TokensPerMonth`
- `RequestsPerDay`
- `OneTimeCredits` (e.g. "$5 free credits, never resets")
- `AlwaysFreeWithLimits` (e.g. HF Inference: free with rate caps but no expiry)

The catalog is human-curated initially. The agent pipeline can SUGGEST updates (it already discovers free tiers as part of its research mission for the dashboard) but every catalog change requires a human-reviewed PR. NEVER auto-merge.

## Routing strategy (`router.py`)

For each call:

1. Pull all `ProviderEntry` for the modality.
2. Filter out entries where the env var is missing.
3. Filter out entries flagged `disabled_until: <date>` (set by the auto-disable loop after 3 consecutive failures).
4. Filter out entries that have hit today's cap in `quotas.py`.
5. Sort by:
   - `last_success_ratio` (descending — prefer providers that worked recently)
   - `speed_tier` (fast first when caller didn't override)
   - catalog declared priority
6. Try each in order. On 4xx (except 408/429): mark provider failed for this run, move on. On 429 / 408 / 5xx: respect Retry-After if present, then move on.
7. On full chain exhaustion: raise `AllProvidersExhaustedError(chain_attempted)`.

All retries + exponential backoff happen INSIDE the per-provider attempt (LiteLLM handles this). The router never retries the same provider twice — falling through is the retry strategy.

## Quotas (`quotas.py`)

Persistent per-provider, per-day counter, persisted to `data/freellm/quotas.json` (or `${FREELLM_QUOTA_DIR}/quotas.json`).

```jsonc
{
  "groq:llama-3.3-70b-versatile": {
    "date": "2026-04-26",
    "requests_used": 412,
    "tokens_used": 86_220,
    "consecutive_failures": 0,
    "last_success_at": "2026-04-26T11:42:18Z"
  }
}
```

Reset rules:
- Daily quotas reset at the provider's documented reset time (most reset at 00:00 UTC; some at midnight Pacific). Catalog entries declare `reset_zone`.
- Monthly quotas reset on the 1st of the month, provider's TZ.
- One-time credits: never reset. When exhausted, provider auto-disabled.

The counter increments on EVERY call attempt — including failed ones — because some providers count failures against quota. When the provider returns the actual usage in the response, the counter is reconciled.

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

## CLI usage (`python -m freellm`)

```bash
# Show the catalog
python -m freellm catalog

# Show the catalog for one modality
python -m freellm catalog --modality text

# Show the routing plan for a request without making the call
python -m freellm plan --modality text --task-name extract-record

# Make a one-shot call
python -m freellm call --modality text --task-name test "Summarize: ..."

# Test the chain (smoke test — sends a 1-token request to each provider in order)
python -m freellm smoke-test

# Show quota state
python -m freellm quotas
```

## Never do (anti-patterns)

- Import `litellm` outside `freellm/router.py`.
- Add a paid model to a `FREE_*` chain without `LLM_ALLOW_PAID=1` opt-in.
- Read API keys from anything except env vars.
- Persist chat history outside the caller's request — the router is stateless.
- Couple `freellm/` to project-specific code (`agents/`, `pipeline/`, `collectors/`). One-way: those import freellm; freellm imports nothing project-local.
- Retry the same provider in a tight loop — falling through to the next provider IS the retry.
- Silently cap costs (raise instead — silent caps cause weird bugs).

## Why not just use LiteLLM directly?

LiteLLM has fallback chains, sure. What `freellm/` adds:
- Curated free-tier catalog with usage metadata (so we KNOW which models are free without trial-and-error).
- Persisted per-provider quota tracking (LiteLLM doesn't track this across runs).
- Modality-aware routing (different chains per modality, not one chain that mixes them).
- Vendor-neutral API for multimodal beyond LLM (image_gen, video_gen, stt, tts).
- A CLI for inspecting / testing the chain.
- A "dry run" / "plan" mode for the dashboard's "Test the chain" UX.

`freellm/` IS a thin layer over LiteLLM. The thinness is the point. It's the curated free-tier knowledge + quota state, nothing more.
