# Project Rule: Agentic Pipeline + LiteLLM Patterns

> Binds every LLM call, agent, scheduler, and pipeline orchestrator. Goal: zero LLM spend, vendor-neutral framework choice, resilient to provider quota exhaustion, manually re-runnable.

## Core stack (LOCKED)

- **Python 3.11+** (entire project)
- **LiteLLM** under the hood. Every LLM call goes through `freellm/` (the in-repo router) which is the **only** package allowed to import `litellm`. Agents import from `freellm`, never from `litellm` directly.
- **Async-first.** All collectors + agents + router are `async def`. `httpx.AsyncClient`, not `requests`.

Why this layering:
- `freellm/` owns the free-tier catalog, fallback chain, and quota state.
- `agents/` calls `freellm.call_text(...)` / `freellm.call_vision(...)` / etc. — clean separation.
- Splitting `freellm/` into a standalone PyPI package later requires zero `agents/` changes.

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
- `response_model` (Pydantic v2) → validated structured output via LiteLLM's `response_format`. Use it whenever the agent extracts a record.
- `LLMResult` carries: `content`, `model_used`, `provider_used`, `latency_ms`, `tokens_in`, `tokens_out`, `parse_confidence`.
- The wrapper retries up to 2 times per provider, then falls through to the next provider in the chain. Total budget: ≤ 6 provider attempts per call.
- On full chain exhaustion: raise `AllProvidersExhaustedError`. Caller decides whether to abort the run or skip that record.

## Agent inventory (locked roles — names match `project-idea.md`)

Every agent is a function in `agents/`, NOT a class hierarchy. No LangGraph / CrewAI unless `/design` justifies the dependency.

| Agent | Purpose | Output | Free-LLM call? |
|---|---|---|---|
| `research.py::find_candidates` | Search-driven discovery of new providers / changed offers | list of candidate URLs + provenance | yes |
| `extractor.py::extract_record` | Parse a candidate page → canonical provider record (Pydantic-validated) | one record OR `parse_confidence: low` | yes |
| `tier_classifier.py::assign_tiers` | Decide `use_case_tiers` for a record using the rubric in `provider-schema.md` | tier list + rationale | yes |
| `change_detector.py::diff_against_last` | Compare today's record vs latest history row, classify change | `changed_fields: [...]`, `change_severity` | no — pure code |
| `verifier.py::queue_low_confidence` | Push `parse_confidence: low` records into a human-review queue | DB write | no |

Each agent has its own file. Each has a focused system prompt stored next to the code (`agents/prompts/<agent>.md`), versioned in git. **Never inline a system prompt > 5 lines in code** — promote to `prompts/<agent>.md`.

## Scheduling

### Daily background run (default)
- **GitHub Actions cron**: `.github/workflows/daily-pipeline.yml`, runs `python -m pipeline.run` once per day, ~02:00 UTC + 10 min jitter.
- Free runner minutes are sufficient (job target ≤ 30 min).
- Secrets injected via repo Actions secrets (the env vars listed above).
- Output: append-only JSON snapshot committed by the workflow under `data/snapshots/<YYYY-MM-DD>.json`. PR-based commit with squash-on-no-change.

### Manual run
- `python -m pipeline.run --providers groq,openrouter` (subset)
- `python -m pipeline.run --since 2026-04-01` (re-scrape everything changed since a date)
- `python -m pipeline.run --background` (detach, write logs to `data/logs/<run-id>.jsonl`, return PID)

### Background-friendly design (mandatory)
- Pipeline writes a `runs/<run-id>.lock` file on start, removes on clean exit. Refuse to start a second run if a lock exists < 24h old (avoid double-run from cron + manual).
- Idempotent: re-running for the same date produces the same snapshot.
- All long-running calls under `asyncio.timeout(...)`. No silent hangs.
- Structured `structlog` logs to `data/logs/<run-id>.jsonl`. One line per provider per agent.
- Honors `pkill -f "pipeline.run"`: every external call is cancellable.

## Cost + quota guardrails

- Hard cap per run: **5,000 LLM calls total** (across all agents). Run aborts at the cap with a clear log + commit-skip.
- Per-provider per-day cap configurable in `agents/llm.py::PROVIDER_DAILY_CAPS`. Defaults conservative (e.g. Groq: 1000, Gemini: 1500).
- LLM call counter persisted in `data/runs/counters.json` so quota state survives across runs.
- Track and emit cost (LiteLLM gives this) — should be **$0.00** for free providers. Any non-zero entry triggers an alert in the run summary.

## Prompts — quality bar (non-negotiable)

- Every agent prompt is in `agents/prompts/<agent>.md`, with a version number in the file header.
- Prompts include: ROLE, INPUT shape, OUTPUT shape (referenced to the Pydantic model), CONSTRAINTS, FAILURE-MODE instructions ("if you can't extract a numeric quota, return `null` and `parse_confidence: low`; do NOT guess").
- **No "you are a helpful assistant" filler.** Every line earns its tokens.
- Test prompts with `pytest tests/agents/` golden-file fixtures before deploying.

## Anti-patterns (block in review)

- Direct `openai.OpenAI()` / `anthropic.Anthropic()` / `groq.Groq()` import outside `agents/llm.py`.
- LLM call without `task_name`.
- LLM call without a `response_model` for any extraction-style task.
- `temperature > 0` on extraction calls.
- System prompt inlined in Python > 5 lines.
- Calling LLM in a tight loop without batch grouping (use `asyncio.gather` over inputs, not a `for url in urls: await call_llm(...)` serial loop).
- Storing API keys anywhere except env vars.
- Catching `AllProvidersExhaustedError` and silently skipping — must log + counter-increment.
- Adding LangGraph / CrewAI / AutoGen / dspy without `/design` approval (they bring heavy deps for limited gain at this scale).

## Free-provider monitoring

Providers shift their free tiers. The pipeline itself tracks LLM-provider availability:
- `data/llm_providers.json` carries: `model_id`, `last_success_at`, `last_failure_reason`, `consecutive_failures`.
- After 3 consecutive failures, the provider is auto-disabled until manually re-enabled.
- Weekly task: re-run a smoke test against every disabled provider; auto-re-enable on first success.

## Why this pipeline rule exists separately from `scraping-ethics.md`

`scraping-ethics.md` covers HOW we fetch provider data. This rule covers HOW we use LLMs to MAKE SENSE of that data and orchestrate everything. They're orthogonal — both apply to most pipeline files. Read both before editing `pipeline/` or `agents/`.
