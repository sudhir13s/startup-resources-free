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
2. **Agentic discovery + extraction.** Daily GH Actions cron + manual `python -m pipeline.run`. Vendor-neutral agentic stack — direct LiteLLM calls + small in-repo orchestrator. NEVER ties to a single vendor's agent SDK.
3. **`freellm/` router library.** Single source of truth for the free-LLM catalog. Knows every free provider's text / vision / image-gen / video / embedding tier. Routes calls in a quota-aware chain so total spend stays at $0. Reusable as a library outside this project. See [`freellm-router.md`](./.claude/rules/project/freellm-router.md).
4. **Free-LLM-Chain filter** in the dashboard UI — see only the LLM/multimodal providers `freellm/` knows about, with live chain order + quota state + a "test the chain" button that proves the $0 promise.
5. **Human-in-the-loop verify queue.** `parse_confidence: low` records surface in a verify tab with Confirm/Reject keyboard shortcuts.
6. **India-primary, US-grants-included-when-accessible.** See "Geographic + sector lens" section.
7. **Media Generation Benchmark (v0.3+, deferred).** Second sub-product: paste a prompt → see ETA + cost + free-quota + quality across video / image / diagram / voice providers, ranked free-first. Uses the same `freellm/` router. Storyboard mode splits long prompts (e.g. system-design explanations) into scenes for per-scene video gen + ffmpeg merge. Locked spec in [`media-benchmark.md`](./.claude/rules/project/media-benchmark.md). NOT in scope for v0.1 ship-today.

## Stack (all rows LOCKED by user 2026-04-26 unless marked)

| Layer | Choice | Notes |
|---|---|---|
| **Language (backend + agents)** | **Python 3.11+** | LOCKED |
| **Backend API** | **FastAPI** | LOCKED |
| **Frontend** | **Next.js 14+ (App Router) + Tailwind** | LOCKED — Node.js runtime |
| **LLM gateway** | **LiteLLM** | LOCKED |
| **Agentic framework** | **Vendor-neutral. Default = direct LiteLLM + small in-repo orchestrator. If a framework added: Pydantic AI or smolagents (both OSS, model-agnostic). NEVER OpenAI Agents SDK / Claude-only Agent SDK / GCP-required ADK as default.** | LOCKED policy (vendor-lock-free) |
| **Free-LLM router** | **In-repo `freellm/` sub-package — single source of truth for free-tier provider catalog, quota tracker, multimodal routing.** Importable as a library; runnable as a script. Designed so it can be split out to PyPI later. | LOCKED |
| Free LLM providers (text) | Groq, OpenRouter (free models), Together free, Cerebras, Gemini free, HF Inference, Mistral free | live catalog in `freellm/providers.py` |
| Free providers (vision / image / video / embed) | Gemini Flash Vision free, HF Inference, Replicate free quota, fal.ai free, Voyage / Cohere / Mistral free embeddings | live catalog in `freellm/providers.py` |
| Collector / scraper | `httpx` + `playwright` + `selectolax` | locked-by-language |
| Storage | SQLite (single file, append-only history). Postgres only if Render hosting requires it. | LOCKED v1 |
| **Scheduler** | **GitHub Actions cron (daily ~02:00 UTC + jitter) + manual `python -m pipeline.run`** | LOCKED |
| **Hosting** | **Render** (FastAPI service + Postgres if needed). NOT Vercel. NOT Fly. | LOCKED |
| Frontend hosting | Render Static Site OR Render Web Service. Stay on Render-only to keep one provider. | LOCKED |
| Observability | structlog → JSON logs in repo (v1). Grafana Cloud free tier later if quota-history charting demanded. | LOCKED v1 |
| License | MIT for code, CC-BY-4.0 for data snapshots | proposed (confirm before public release) |

Phasing note: user **rejected v0 / v0.5 staging.** Build directly to v1. No Streamlit dogfooding step. No "ship in two hours" optimism baked into estimates — `/design` will produce a realistic task list.

## Dashboard layer (LOCKED — direct v1)

User decision 2026-04-26: skip Streamlit / Metabase / phased approach. Build **Next.js 14 + Tailwind + FastAPI** directly.

- **Frontend**: Next.js 14 App Router + Tailwind + shadcn/ui (or equivalent OSS component library — Radix-based, no vendor lock).
- **Backend**: FastAPI exposing `/api/providers`, `/api/changes`, `/api/run` (manual trigger), `/api/verify-queue`.
- **Hosting**: Render — one Web Service for FastAPI, one Static Site OR Web Service for Next.js. GitHub Actions handles cron.
- **Charts**: Recharts (React) for the in-app timeline. NO Grafana embed in v1 (revisit if needed).
- **Filters in UI** (LOCKED): tier chips (`hobby` / `personal` / `startup-mvp` / `startup`), category multi-select, region selector with India default, **Free-LLM-Chain mode** (see below), parse-confidence threshold, status filter.

### Free-LLM-Chain filter (new, LOCKED)

A dedicated UI mode separate from the tier filter. When ON:

- Catalog filters to **only the LLM / multimodal providers** the in-repo `freellm/` router knows about.
- A side panel shows the **routing chain**: order of providers, current quota state, last successful call timestamp.
- Provider cards show "Use this for: text / vision / image-gen / embed / video" pills.
- A "Test the chain" button runs a small free call through the chain and reports which provider answered.

This is the "$0 spend" promise made visible.

### What NOT to build

- Vercel anything (user explicit reject).
- Grafana as the main UI (still wrong shape; only embed if `/design` justifies a single timeline panel later).
- Streamlit (skipped per user decision).
- Multiple frontends.

## Project structure (target — v1)

```
startup-resources-free/
  freellm/            ← in-repo free-LLM router library (LiteLLM wrapper, quota tracker, multimodal routing)
    __init__.py
    providers.py      ← canonical free-provider catalog (text/vision/image/video/embed)
    router.py         ← fallback chain + quota-aware planner
    quotas.py         ← per-provider per-day cap tracking (persisted)
    schemas.py        ← Pydantic models (TextRequest, VisionRequest, ImageGenRequest, EmbedRequest, …)
    cli.py            ← `python -m freellm` script entry
    prompts/
  agents/             ← LLM agents (extractor, tier-classifier, change-detector). Imports freellm/, NOT litellm.
    research.py
    extractor.py
    tier_classifier.py
    change_detector.py
    verifier.py
    prompts/          ← versioned system prompts
  collectors/         ← scrapers per provider (one file per provider)
    cloud/  gpu/  ai_apis/  databases/  storage/  credits/  grants/  accelerators/  perks/  oss/
  pipeline/           ← orchestration: schedule, run, diff, alert, write
    __main__.py       ← `python -m pipeline.run`
    run.py
  api/                ← FastAPI service: /api/providers, /api/changes, /api/run, /api/verify-queue
    main.py
    routes/
    deps.py
  schema/             ← Pydantic record models, SQL migrations, VERSION
  frontend/           ← Next.js 14 App Router + Tailwind + shadcn/ui — the dashboard
    app/
    components/
    lib/
  data/
    snapshots/<date>.json   ← weekly committed snapshot
    raw/<provider>/         ← gitignored raw scraped HTML/JSON
    logs/<run-id>.jsonl
    runs/                   ← lock files, counters
  docs/
    plans/  architecture/  discussions/  diagrams/
    design-prompt.md        ← prompt for design tools / designer LLMs
  tests/
  .github/workflows/
    daily-pipeline.yml      ← cron + manual dispatch
    ci.yml
  .claude/
    rules/project/
  pyproject.toml
  package.json              ← Next.js workspace
  render.yaml               ← Render service definition
  README.md
  CLAUDE.md
  LICENSE                   ← MIT for code
```

Until scaffolded, only docs exist. `/design` produces the task list that creates the tree above.

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

## SHIP-TODAY plan (LOCKED 2026-04-26 by 3-specialist roundtable)

User mandate: deployed-on-Render basic version in **~2 hours from 12:06 IST**. 3-specialist consensus (architect + frontend + designer) cut scope to:

### What ships TODAY (call this `v0.1-seed`)

1. **Hardcoded seed** at `data/seed.json` — 15-20 hand-curated provider records. Fields: `id, name, category, tiers[], geo_priority, india_accessible, headline, free_tier_summary, source_url, parse_confidence, last_verified_at`. NO scraping. NO LLM calls. NO SQLite.
2. **FastAPI**: ONE file `api/main.py`, ONE route `GET /api/providers?tier=&india=` reading + filtering the seed JSON. `/api/health`. Uvicorn entry. CORS-allow the Next.js origin.
3. **Next.js 14 App Router** (Lovable-redesign 2026-04-26): TopBar (logo + nav + ⌘K search + status pill + Run-now + theme toggle) · left Sidebar (tier radio + category checkboxes + offer-type checkboxes + region select + parse-confidence buttons + Reset) · main with SubTabs (Catalog active, Compare/Changes/Verify SOON) · Provider cards with three stat tiles (Free Quota / Duration / Region), tier-fit pill, offer + eligibility, Source link, Details expand, parse-confidence dot, freshness footer.
4. **Theme**: light + dark via `next-themes` (CSS variables, `class` attribute on `<html>`). Default dark, system-aware, toggle in TopBar right side. Both palettes contrast-checked.
5. **Tab bar in nav**: 4 labels rendered, but Compare/Changes/Verify are visually muted with `Coming soon` tooltip. Click is a no-op.
6. **Detail view**: inline expanded card on click (NOT slide-over, NOT separate route). Faster, no focus-trap accessibility risk.
7. **Render deploy**: `render.yaml` declaring **two Web Services** — FastAPI + Next.js. **NOT Static Site** for Next.js (server components + route handlers require a runtime). Free-tier Render services do NOT share a private network, so frontend calls API via its public Render URL via env var `BACKEND_URL`. CORS_ORIGINS on FastAPI must match the frontend's Render URL exactly.
8. **GH Actions**: ONE workflow `.github/workflows/ci.yml` running `pnpm build` + `pip install + pyright` on PR. NO cron yet.
9. **README, LICENSE (MIT), .env.example, .gitignore**: short, honest, point at the deferred-to-v1 spec.

### What is DEFERRED to v0.2+ (locked spec, not built today)

- The `freellm/` router library + its CLI + multimodal coverage.
- Any agentic pipeline / scraping collectors / `pipeline/` package.
- Compare tab, Changes tab (timeline), Verify queue tab.
- Slide-over panel.
- Light-mode + dark-mode toggle.
- Free-LLM-Chain filter mode (depends on `freellm/`).
- Category multi-select filter (tier filter + India badge sufficient for v0.1).
- Recharts / any charting library.
- SQLite / Postgres migration.
- GitHub Actions cron + agent run.
- Verify-confidence keyboard shortcuts.

The deferred items are LOCKED in `CLAUDE.md` + `.claude/rules/project/*.md` so the next session picks up where v0.1 stopped — nothing about the spec was given up, only sequenced.

### Time budget (target)

| Block | Target | Notes |
|---|---|---|
| Q&A (this turn ↔ user) | 5 min | GitHub repo + Render account confirmation |
| Repo scaffold (next/fastapi/shadcn init, commits) | 25 min | First 25 min of next turn |
| Seed data + FastAPI route | 15 min | |
| Next.js components + page | 50 min | Bulk of the time |
| Render setup + deploy + smoke test | 25 min | Includes DNS / cold-start verification |
| README + commit + push | 10 min | |
| **Total** | **~130 min** | Tight. Realistic only if user answers questions immediately. |

If any block exceeds budget by > 50%, STOP and reassess scope — don't push the v0.1 cut further.

### Open risks (called out before starting)

- Render free Web Service cold-start ~30-60 s on first hit. **Both** services cold-start independently. Acceptable for demo; document in README + add a "warm the API" curl ping in pre-demo prep.
- Free-tier Render services spin down after 15 min idle.
- Without a custom domain, dashboard URL is `*.onrender.com`.
- **Env-var circular dependency** (DevOps flag): Frontend needs API URL; API needs frontend URL for CORS. Both services must be NAMED first in `render.yaml`, then URLs derived as `https://<name>.onrender.com`, then both env vars set in Render dashboard BEFORE first deploy. Failure mode: deploy succeeds but CORS rejects all calls.
- Seed data accuracy: 15 hand-picked records sourced from public free-tier pages today. Mark `last_verified_at: 2026-04-26` and `parse_confidence: high` only after a manual click-through.
- One specialist (designer) suggested `/provider/[slug]` static route for detail view; downgraded to inline-expand for time. Promote to a route in v0.2 when slide-over goes in.

### `/release` verification checklist (CRITICAL findings — must all pass before ship)

Confidence 8+ findings from 2026-04-26 roundtable. Every box MUST be ticked before `/release`.

- [ ] **A1-4** — Catalog-only scope; no agentic / SQLite / cron / 3-tabs in v0.1 (Architect)
- [ ] **F-B1** — `GET /api/providers` route exists, returns seed JSON (Frontend)
- [ ] **F-B2** — Next.js 14 App Router project initialized with TS strict + Tailwind (Frontend)
- [ ] **D-B1** — Tier filter (Lovable-style sidebar radio list, 6-tier scheme: hobby/personal/startup-mvp/pre-seed/seed/series-a) renders with `personal` pre-selected on first paint; grid renders filtered cards immediately. (User override 2026-04-26: was `hobby`, then redesign added 6 tiers, default became `personal`.)
- [ ] **D-B2** — Skeleton pulse cards render during data fetch — no empty white screen (Designer)
- [ ] **D-B3** — 4.5:1 contrast verified on body text + ≥3:1 on large text (Designer)
- [ ] **DO-B1** — Next.js is `type: web` not `static-site` in render.yaml (DevOps)
- [ ] **DO-B2** — `BACKEND_URL` (frontend) + `CORS_ORIGINS` (api) set in Render dashboard before first deploy; both URLs derived from `name:` fields BEFORE deploy (DevOps)

Plus standard `/release` gates (QA, Security, DevOps, Docs).

## Dependency-update workflow (auto-pilot)

`.github/dependabot.yml` opens weekly PRs (Mon 06:00 IST) grouped by stack:

- `python-runtime` (fastapi, uvicorn, pydantic) — minor + patch only.
- `python-dev` (pytest, ruff, httpx) — minor + patch only.
- `next-stack` (next, next-themes, eslint-config-next) — minor + patch only.
- `react-stack` (react, react-dom, @types/react) — minor + patch only.
- `tailwind-stack` (tailwindcss, tailwind-merge, autoprefixer, postcss) — minor + patch only.
- `radix-stack` (@radix-ui/*, class-variance-authority, clsx, lucide-react) — all bumps allowed.
- `dev-tooling` (eslint, typescript, @types/node) — minor + patch only.
- `github-actions` — all bumps allowed.

Major bumps for the lockstep deps (`next`, `react`, `react-dom`, `eslint*`, `tailwind*`, `typescript`, `@types/node`, `@types/react*`, `autoprefixer`, `postcss`, `fastapi`, `pydantic`, `uvicorn`, `pytest`, `ruff`) are **blocked** at dependabot level — they require coordinated upgrade PRs (e.g. Next 15/16 cutover) so they don't break CI in solo bumps.

`.github/workflows/dependabot-auto-merge.yml` watches CI completion and, when a Dependabot PR's CI finishes green, approves + squash-merges + deletes the branch immediately. Free-tier private repos don't get GitHub's native auto-merge UI; this workflow_run-triggered approach replaces it without paid plan.

End result: dependency PRs flow Dependabot → CI → auto-merge → main → Render auto-deploys, hands-off.

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

## Repo state (as of 2026-04-26)

- Git repo initialized 2026-04-26.
- GitHub remote: pending — user authorized push, but repo name + visibility await confirmation.
- No `package.json` / `pyproject.toml` yet — scaffold during `/design` → `/build`.
- Files present: `project-idea.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `docs/design-prompt.md`, `.claude/rules/project/*`, `.gitignore`.
- Personal scope, India-primary. CI via GitHub Actions. Deploy to Render.

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
