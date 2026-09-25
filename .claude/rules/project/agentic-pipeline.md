# Project Rule: Refresh Pipeline + freellm Patterns

> Binds every LLM call, the refresh runner, and the on-demand pipeline. Goal: zero LLM spend, vendor-neutral framework choice, resilient to provider quota exhaustion, manually re-runnable.

## Core stack (LOCKED — architecture v2, 2026-09-25)

- **Python 3.12** (entire project)
- Every LLM call goes through `freellm/` (the in-repo router), which owns the **only**
  OpenAI-compatible `httpx` backend (`freellm/backend.py`) — chosen over LiteLLM so the API
  fits Render's 512 MB free instance. `refresh/` and `api/` import from `freellm`, never call
  a provider SDK or a raw HTTP client for LLM traffic directly. LiteLLM is not a runtime
  dependency; it may be used ad hoc for local experimentation only.
- **Async-first.** `refresh/` and `freellm/` are `async def` throughout. `httpx.AsyncClient`,
  not `requests`.

Why this layering:
- `freellm/` owns the free-tier catalog, fallback chain, and quota state (via an injected
  `StateStore` — the API's SQLite repository in production, an in-memory store in tests).
- `refresh/extract.py` and friends call `freellm.call_text(...)` / `freellm.call_vision(...)` —
  clean separation.
- Splitting `freellm/` into a standalone PyPI package later requires zero `refresh/` changes.

## Vendor-neutrality (LOCKED policy)

User mandate 2026-04-26: **no vendor-locked agentic framework as the default.**

| Framework | Default? | Rationale |
|---|---|---|
| Direct LiteLLM + small in-repo orchestrator | **YES (default)** | Zero deps beyond what we already need. No lock. |
| **Pydantic AI** | Allowed if `/design` justifies | OSS, model-agnostic via LiteLLM, validates outputs. Light footprint. |
| **smolagents** (HuggingFace) | Allowed if `/design` justifies | OSS, model-agnostic, HF-backed but not HF-locked. |
| **LangGraph** | Allowed only if state-machine complexity demands it | Heavy. Acceptable but rarely needed at this scale. |
| **Google ADK** | Allowed ONLY if zero GCP login required for our workflow | If ADK can run with non-GCP keys + non-Gemini models via LiteLLM, it qualifies. Verify before adopting. |
| **Anthropic Claude Agent SDK** | NO as default | Claude-specific abstractions. Use only if user explicitly opts in. |
| **OpenAI Agents SDK** | NO | OpenAI-locked by default. |
| **CrewAI / AutoGen / dspy** | Case-by-case | OSS, multi-model, but each adds 50-200 transitive deps. Justify before pulling in. |

**Rule:** before adding ANY agent framework dependency, write a short ADR under `docs/adr/<NNN>-agent-framework-<name>.md` listing: what specific feature is needed, what the OSS / vendor-lock posture is, what we lose if we drop it later. `/design` reviews + locks the choice.

Code-level enforcement:
- `pyproject.toml` `[tool.deps-policy]` lists allowed agentic deps. CI fails if a banned package appears in `pyproject.toml` / lockfile without an accompanying ADR.

## Free-provider fallback chain (lives in `freellm/providers.py`)

Single source of truth for the catalog. Agents do NOT redefine this list. See [`freellm-router.md`](./freellm-router.md) for details. Short summary:

- Modalities covered: `text`, `vision`, `image_gen`, `video_gen`, `embedding`, `audio_stt`, `audio_tts`.
- Per modality: an ordered list of `(provider, model, free_tier_metadata)` records.
- Provider keys via env vars only (`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `HF_TOKEN`, `CEREBRAS_API_KEY`, `MISTRAL_API_KEY`, `REPLICATE_API_TOKEN`, `FAL_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY`). Missing key → provider dropped at startup with one log line.
- A paid key (e.g. `OPENAI_API_KEY`) is allowed but never auto-inserted. Opt-in via `LLM_ALLOW_PAID=1`.

## The wrapper contract (`freellm/router.py`)

```python
async def call_llm(
    *,
    messages: list[dict],
    model_chain: list[str] | None = None,   # default = FREE_PROVIDERS
    response_model: type[BaseModel] | None = None,  # Pydantic = structured output
    max_tokens: int = 2000,
    temperature: float = 0.0,
    timeout_s: int = 60,
    task_name: str,                          # required, for logs + cost tracking
) -> LLMResult: ...
```

- Always-required: `messages`, `task_name`.
- `temperature=0.0` default — extraction tasks don't want randomness.
- `response_model` (Pydantic v2) → validated structured output, enforced by the OpenAI-compatible
  backend's JSON mode. Use it whenever `refresh/extract.py` extracts a record.
- The actual public functions live in `freellm/router.py` (`call_text`, `call_vision`,
  `call_embed` — see `freellm-router.md` for the full contract). This section states the usage
  rules for callers; the contract itself is not duplicated here.
- The router retries up to 2 times per provider, then falls through to the next provider in the
  chain, with automatic cooldown rotation on rate limits. On full chain exhaustion it raises
  `AllProvidersExhaustedError`; the caller decides whether to abort the run or skip that record.

## Refresh module inventory (`refresh/` — replaces the old `agents/` package)

Every stage is a module-level function in `refresh/`, not a class hierarchy. No LangGraph /
CrewAI unless `/design` justifies the dependency.

| Module | Purpose | Output | Free-LLM call? |
|---|---|---|---|
| `discover.py` | Search-driven discovery of new providers via the search chain (`search.py`) | candidate URLs + provenance, queued for review | yes (search, not LLM) |
| `fetch.py` | Polite HTTP fetch: robots.txt, 30s/host, conditional GET, Jina Reader fallback | page text + hash | no |
| `extract.py` | Parse fetched text → canonical `ProviderRecord` candidate (Pydantic-validated) | one record OR `parse_confidence: low` | yes |
| `merge.py` | Never-degrade merge of the candidate against the current record | accepted version + field diff, or no-op | no — pure code |
| `runner.py` | Orchestrates fetch → hash-gate → extract → merge → discover per run | `RunReport` (`domain/runs.py`) | orchestration only |

Each module has a focused system prompt for its LLM call stored next to the code
(`refresh/prompts/<module>.md` when a prompt exceeds 5 lines), versioned in git. **Never inline
a system prompt > 5 lines in code.**

## Scheduling (architecture v2 — button-triggered, no cron)

- **Trigger**: `POST /api/refresh` from the frontend's Refresh button (admin-token gated). The
  API starts `refresh.runner.create_runner(repo)` as a background task inside the same Render
  process — there is no scheduled job, GitHub Actions cron, or separate worker.
- **CLI (local/manual only)**: `python -m refresh run [--providers ...] [--discover] [--force]`
  and `python -m refresh search-status` (`refresh/__main__.py`). Not used in production.
- **Persistence**: a run's accepted changes are written to the SQLite repository; on completion
  `storage/github_sync.py` pushes the database to the `data` git branch. `main` is never
  touched by a refresh, so there is no redeploy per run.
- **Idempotent**: the hash gate (page-content hash vs. the last successful fetch) skips
  extraction entirely for an unchanged page, so re-running costs near-zero LLM calls.
- **Cancellable**: long-running calls run under `asyncio.timeout(...)`; the API can cancel the
  background task on shutdown (`app.state.background_tasks`, see `api/main.py`).

## Cost + quota guardrails

- Hard cap per run: `RefreshOptions.max_llm_calls` (`domain/runs.py`), default 200 via the CLI,
  configurable per call. A run aborts at the cap with a clear log entry.
- Per-provider quota is tracked through `freellm/quotas.py`'s injected `StateStore` — the API's
  SQLite repository in production — so quota state survives restarts and redeploys.
- Cost should be **$0.00** for every free-tier call. `LLM_ALLOW_PAID=1` is required before any
  paid key is used; unset by default.

## Anti-patterns (block in review)

- Direct provider-SDK or raw-HTTP import for LLM traffic outside `freellm/backend.py`.
- LLM call without `task_name`.
- LLM call without a `response_model` for any extraction-style task.
- `temperature > 0` on extraction calls.
- System prompt inlined in Python > 5 lines.
- Calling LLM in a tight loop without batch grouping (`asyncio.gather` over inputs, not a
  `for url in urls: await call_text(...)` serial loop).
- Storing API keys anywhere except env vars.
- Catching `AllProvidersExhaustedError` and silently skipping — must log the outcome on the
  `RunReport`.
- Adding LangGraph / CrewAI / AutoGen / dspy without `/design` approval.
- Reintroducing a cron / scheduled workflow for refresh — the button-triggered, in-process
  design is locked (architecture v2, 2026-09-25); see `hosting-migration.md` for why.

## Free-provider monitoring

Providers shift their free tiers. `freellm/quotas.py` tracks per-provider state (last success,
consecutive failures) through the injected `StateStore`; after repeated consecutive failures a
provider is skipped for the rest of the chain rotation until it succeeds again.

## Why this pipeline rule exists separately from `scraping-ethics.md`

`scraping-ethics.md` covers HOW we fetch provider data. This rule covers HOW we use LLMs to MAKE SENSE of that data and orchestrate everything. They're orthogonal — both apply to most refresh files. Read both before editing `refresh/` or `freellm/`.
