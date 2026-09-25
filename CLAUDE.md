# startup-resources-free — Project CLAUDE.md

> Project-local rules. Extends global `~/.claude/CLAUDE.md` (router + ETHOS + always-on guardrails). Project rules beat global on conflict.

## What this project is

A personal-first **resource intelligence dashboard** that aggregates free / discounted / time-limited offerings across:

- Cloud + hosting (AWS / GCP / Azure / Oracle / Fly.io / Render / Railway / Vercel / Netlify free tiers)
- GPU + AI compute (Colab / Kaggle / RunPod / Lambda / Vast.ai / Paperspace)
- AI APIs + free model quotas (Groq / OpenRouter / Together / HF Inference / Replicate)
- Databases (Supabase / Neon / Mongo Atlas / PlanetScale / Redis Cloud)
- Startup credits + perks (AWS Activate / GCP for Startups / Azure for Startups / Notion / HubSpot / Stripe Atlas)
- Grants + non-dilutive funding (govt, sector-specific, India-focused)
- OSS goldmines (boilerplates, agent frameworks, founder tooling)

Source: [`project-idea.md`](./project-idea.md) (full brainstorm).

## Display name

**ResourceOS** — locked by user 2026-04-26 (chosen over FounderOS / FreeStack Radar / Infra Compass / Resource Command Center). Repo slug remains `startup-resources-free`. UI title, README header, and FastAPI `/api/health` `service_name` all read **ResourceOS**.

## Goal posture (important)

Personal dashboard FIRST, optionally shareable later. **Not** a startup pitch yet. Design choices favor:

- Cheap to run (free-tier stack only).
- Easy to maintain solo.
- Append-only data history (so we can see when a free tier shrunk).
- Resilience to provider scraping changes.

If `/validate` later flips this to a public product (FreeStackHub.com angle), update this file.

## Headline features (LOCKED by user 2026-04-26)

1. **Use-case tier filter.** Sidebar radio list (Lovable-style). 6-tier scheme:
   - `hobby` — weekend tinkering, learning, throwaway demos
   - `personal` — small personal site / tool, single user, always-on
   - `startup-mvp` — pre-revenue prototype, ~10-1000 users, easy upgrade path
   - `pre-seed` — bootstrapped or friends-and-family-funded, early traction
   - `seed` — post-seed round, $0.5–5M raised
   - `series-a` — post-Series A, paying users + production scale
2. **Agentic discovery + extraction.** Refresh-button-triggered, in-process (`refresh/runner.py`) — no cron. Vendor-neutral agentic stack — direct calls through `freellm/` + a small in-repo orchestrator. NEVER ties to a single vendor's agent SDK.
3. **`freellm/` router library.** Single source of truth for the free-LLM catalog. Knows every free provider's text / vision / embedding tier (image-gen / video / audio remain dry-run only, deferred to the Media Benchmark). Routes calls in a quota-aware chain — with automatic cooldown rotation on rate limits — over a plain OpenAI-compatible `httpx` backend, so total spend stays at $0. Reusable as a library outside this project. See [`freellm-router.md`](./.claude/rules/project/freellm-router.md).
4. **Free-LLM Chain page** in the dashboard — see the LLM providers `freellm/` knows about, with catalog + plan endpoints exposed via `api/routers/freellm_router.py`. Live "test the chain" UX is not yet built; the API surface is.
5. **Human-in-the-loop verify queue.** `parse_confidence: low` records and discovery candidates surface on the Candidates page for approve/reject. `data/providers_seed.json` is also a hand-correction channel — an edited seed entry is re-applied on the next boot, diffed on the Changes page, while unchanged entries never overwrite what a refresh has since learned (see `storage/seed_import.py`).
6. **India-primary, US-grants-included-when-accessible.** See "Geographic + sector lens" section.
7. **Media Generation Benchmark (v0.3+, deferred).** Second sub-product: paste a prompt → see ETA + cost + free-quota + quality across video / image / diagram / voice providers, ranked free-first. Uses the same `freellm/` router. Storyboard mode splits long prompts into scenes for per-scene video gen + ffmpeg merge. Locked spec in [`media-benchmark.md`](./.claude/rules/project/media-benchmark.md). Not started.

## Stack (all rows LOCKED by user 2026-04-26 unless marked)

| Layer | Choice | Notes |
|---|---|---|
| **Language (backend)** | **Python 3.12** | LOCKED — `pyproject.toml` `target-version = "py312"` |
| **Backend API** | **FastAPI** | LOCKED |
| **Frontend** | **Next.js 14+ (App Router) + Tailwind** | LOCKED — Node.js runtime |
| **LLM gateway** | **`freellm/` over a plain OpenAI-compatible `httpx` backend** (`freellm/backend.py`) | LOCKED (architecture v2, 2026-09-25) — no LiteLLM/sidecar on Render (512 MB free instance); LiteLLM remains optional for local experimentation only, never a runtime dependency of `api/` |
| **Agentic framework** | **Vendor-neutral. Default = direct calls + small in-repo orchestrator (`refresh/runner.py`).** NEVER OpenAI Agents SDK / Claude-only Agent SDK / GCP-required ADK as default. | LOCKED policy (vendor-lock-free) |
| **Free-LLM router** | **In-repo `freellm/` sub-package — single source of truth for free-tier provider catalog, quota-aware routing with cooldown rotation.** Importable as a library; runnable as a script (`python -m freellm`). Designed so it can be split out to PyPI later. | LOCKED |
| Free LLM providers (text/vision/embed, live) | Groq, Gemini, OpenRouter free models, Cerebras, Mistral, SambaNova, NVIDIA, Together, HF Inference | live catalog in `freellm/providers.py` |
| Image-gen / video-gen / STT / TTS | Dry-run only (`Plan`, no live call) | deferred to Media Benchmark (v0.3+) |
| Fetch client | `httpx` (polite fetch: robots.txt, 30s/host, ETag/Last-Modified, Jina Reader fallback) | `refresh/fetch.py` |
| Storage | SQLite, single file, append-only version history per provider. Persisted on a dedicated `data` git branch (not `main`) — pulled on API boot, pushed after each refresh. Postgres not adopted. | LOCKED (architecture v2) |
| **Scheduler** | **Refresh button → runs in-process inside the Render API service on click. No cron, no GitHub Actions pipeline.** A CLI (`python -m refresh run`) exists for local manual runs only. | LOCKED (architecture v2, 2026-09-25) |
| **Hosting** | **Render** (two free Web Services: API + frontend). NOT Vercel. NOT Fly. | LOCKED |
| Frontend hosting | Render Web Service (server routes required — not a Static Site). | LOCKED |
| Observability | Structured JSON logs (Python `logging`) to stdout, captured by Render. | LOCKED v2 |
| License | MIT for code | LOCKED |

## Dashboard layer (architecture v2, 2026-09-25)

- **Frontend**: Next.js 14 App Router + Tailwind + shadcn/ui (Radix-based, no vendor lock). Pages: Catalog (`app/resources`), Grants & Credits (`app/funds`), Compare (`app/compare`), Changes (`app/changes`), Runs (`app/runs`), Candidates (`app/candidates`), Free-LLM Chain (`app/freellm`).
- **Backend**: FastAPI (`api/main.py`) with routers for providers (facets + detail), changes, runs, refresh (start/status), candidates (approve/reject), and freellm (catalog/plan). Admin endpoints require `X-ResourceOS-Passphrase`.
- **Admin auth**: passphrase login via Next.js server routes (`frontend/app/api/admin/*`) sets an httpOnly session cookie in the browser; the server route alone holds `RESOURCEOS_PASSPHRASE` and forwards it to the API. The token never reaches client-side JS.
- **Refresh trigger**: a button in the UI, not a schedule. See "Headline features" above and `.claude/rules/project/agentic-pipeline.md`.
- **Filters in UI**: use-case tier (6-tier scheme), service-aware category facets with live counts, region/India-accessible, offer-type, parse-confidence.

### What NOT to build

- Vercel anything (user explicit reject).
- Grafana as the main UI.
- Streamlit.
- Multiple frontends.
- A GitHub Actions cron pipeline for refresh (button-triggered, in-process only — see Stack table).

## Project structure (current — architecture v2)

```
startup-resources-free/
  domain/     ← shared types: records.py (ProviderRecord v2 — services[]/credits[]/claim_steps/
                links + computed categories/card_variant/india_accessible), filters, changes,
                runs, taxonomy
  storage/    ← repository.py (Repository protocol), sqlite_repository.py, migrations.py,
                seed_import.py (re-applies a changed seed entry every boot, never overwrites
                refreshed data), github_sync.py (pulls/pushes resourceos.db to the `data` branch)
  freellm/    ← __init__.py (public API: call_text/call_vision/call_embed live; image/video/
                stt/tts dry-run), providers.py (catalog), backend.py (OpenAI-compatible httpx,
                no LiteLLM/sidecar), router.py (fallback chain + cooldown rotation), quotas.py
                (StateStore protocol), schemas.py, errors.py, cli.py
  refresh/    ← fetch.py (robots.txt, 30s/host, ETag, Jina fallback), extract.py (free-LLM
                extraction), merge.py (never-degrade merge), discover.py + search.py (Tavily →
                Exa → Jina → Linkup → SerpAPI), runner.py (create_runner — what the API calls),
                __main__.py (`python -m refresh run|search-status`, local/manual only)
  api/        ← main.py (create_app; lifespan pulls data branch, migrates, imports seed,
                configures freellm), settings.py, routers/ (providers, changes, runs, refresh,
                candidates, freellm_router, health), services/ (refresh_service, catalog_service)
  frontend/   ← app/ (resources, funds, compare, changes, runs, candidates, freellm pages;
                api/admin/ — passphrase login/session/refresh/candidate actions, server-only),
                components/, lib/
  data/
    providers_seed.json  ← 74 curated v2 records; hand-correction channel (storage/seed_import.py)
  docs/       ← plans/ architecture/ discussions/ progress/
  .github/workflows/  ← ci.yml (manual: gh workflow run ci.yml)
  .claude/rules/project/
  pyproject.toml   ← testpaths: domain, storage, freellm, refresh, api
  requirements.txt  requirements-dev.txt
  package.json     ← frontend workspace (frontend/package.json)
  render.yaml      ← two Web Services: API (Python) + frontend (Node)
  README.md  CLAUDE.md  LICENSE (MIT)
```

## Project-local rules

| Trigger context | File |
|---|---|
| Writing/editing any collector or extractor | [.claude/rules/project/scraping-ethics.md](./.claude/rules/project/scraping-ethics.md) |
| Writing/editing the provider record / schema | [.claude/rules/project/provider-schema.md](./.claude/rules/project/provider-schema.md) |
| Writing/editing any LLM call, agent, or pipeline orchestrator | [.claude/rules/project/agentic-pipeline.md](./.claude/rules/project/agentic-pipeline.md) |
| Writing/editing `freellm/` (the free-LLM router library) | [.claude/rules/project/freellm-router.md](./.claude/rules/project/freellm-router.md) |
| Writing/editing the Media Benchmark dashboard (v0.3+) | [.claude/rules/project/media-benchmark.md](./.claude/rules/project/media-benchmark.md) |
| Migrating off Render (any host change) | [.claude/rules/project/hosting-migration.md](./.claude/rules/project/hosting-migration.md) |

Global rules from `~/.claude/rules/` still bind. These extend, not replace.

## Dependency updates + CI (manual)

`.github/dependabot.yml` opens weekly PRs (Mon 06:00 IST) grouped by stack. The Python
ecosystem watches `directory: /` (root `pyproject.toml`/`requirements*.txt`) — updated from the
pre-v2 `backend/` layout when that directory was removed; npm still watches `/frontend`.

- `python-runtime` (fastapi, uvicorn, pydantic) — minor + patch only.
- `python-dev` (pytest, ruff, httpx) — minor + patch only.
- `next-stack` (next, next-themes, eslint-config-next) — minor + patch only.
- `react-stack` (react, react-dom, @types/react) — minor + patch only.
- `tailwind-stack` (tailwindcss, tailwind-merge, autoprefixer, postcss) — minor + patch only.
- `radix-stack` (@radix-ui/*, class-variance-authority, clsx, lucide-react) — all bumps allowed.
- `dev-tooling` (eslint, typescript, @types/node) — minor + patch only.
- `github-actions` — all bumps allowed.

Major bumps for the lockstep deps (`next`, `react`, `react-dom`, `eslint*`, `tailwind*`, `typescript`, `@types/node`, `@types/react*`, `autoprefixer`, `postcss`, `fastapi`, `pydantic`, `uvicorn`, `pytest`, `ruff`) are **blocked** at dependabot level — they require coordinated upgrade PRs (e.g. Next 15/16 cutover) so they don't break CI in solo bumps.

CI is **manual only** (owner decision 2026-09-25): `ci.yml` runs on `workflow_dispatch`, never on push or PR, and there is no auto-merge. To check a Dependabot PR or any branch: `gh workflow run ci.yml --ref <branch>`, then `gh run watch`; merge by hand when green.

## Workflow expectations

- **Greenfield.** Run `/validate` (Market + CEO + CTO + Product) BEFORE `/design`. Personal-tool framing changes the demand bar — make sure CEO + Product agree this is worth building vs. just maintaining a Notion list.
- **`/design` outputs go to `docs/architecture/<slug>/<timestamp>-<name>.md`** per `rules/common/specialist-discussions.md` (append-only dated artifacts).
- **`/build`** only after `TODOS.md` is generated by `/design` Phase D.
- Multi-specialist consultations (CEO + CTO + Architect on stack choice) → use `/roundtable`, save to `docs/discussions/<timestamp>-...`.

## Data-source ethics + risk note (non-negotiable)

This project's value depends on scraping public pricing/free-tier pages. Some providers' ToS forbid automated access. Before adding ANY new collector:

1. Read provider ToS / robots.txt.
2. Prefer official APIs (status, pricing, marketplace catalogs) over HTML scraping.
3. Rate-limit aggressively (default: 1 req / 30s per host, weekly cadence — not per-minute).
4. Identify with a real `User-Agent` string + contact email.
5. Cache responses; never re-scrape unchanged pages.

If a provider asks us to stop, stop. Add to a `BLOCKLIST.md` and mark records as `source: manual`. Full rules: [`.claude/rules/project/scraping-ethics.md`](./.claude/rules/project/scraping-ethics.md).

## Geographic + sector lens (user context — LOCKED)

**India-primary.** User is India-based. Ranking + UI defaults bias toward opportunities **available to people in India**.

Coverage rules:

1. **India-native programs** — Startup India, MeitY AI grants, state-level missions (Karnataka, Telangana, Maharashtra, etc.), university / IIT / IISc incubators, NASSCOM 10000 Startups, AIM, Atal Innovation Mission. Always covered. UI default surfaces these.
2. **US / EU / global programs accessible to Indian residents or Indian-incorporated companies** — covered with annotation. Examples: YC (open globally), MIT 100K (open), Mozilla MOSS, OpenAI grants (varies), AWS Activate (global). Tag `geo_priority: accessible-from-india`.
3. **US-only or LP-only programs** — covered with clear "US-residents only" tag. Tag `geo_priority: us-only`. Do NOT default-show to Indian users; surface in a separate "Global / US" tab.
4. **Visa-conditional opportunities** — annotate the visa requirement explicitly. Don't bury it.

Schema field `geo_priority` (added in `provider-schema.md`) carries one of: `india-native | accessible-from-india | global-other | us-only | eu-only | other-region`.

## What this CLAUDE.md does NOT cover

- Code-craft, security, architecture defaults — those are global rules in `~/.claude/rules/common/`.
- Industry standards for Python/TS/Go — global `rules/common/industry-standards.md`.
- Specialist personas + workflows — global trigger maps in `~/.claude/CLAUDE.md`.

## Size budget

This file: keep under 200 lines. If it grows, split into project-rule files and link from here.
