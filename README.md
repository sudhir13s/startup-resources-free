# ResourceOS — startup-resources-free

> **ResourceOS** is a personal-first **resource intelligence dashboard** that aggregates free / discounted / time-limited offerings across cloud, GPUs, AI APIs, databases, hosting, startup credits, grants, and OSS goldmines — and ranks them for **hobby / personal / startup-MVP / startup** projects, India-primary.
>
> Repo slug: `startup-resources-free`. Product display name: **ResourceOS**.

**Status: pre-code — `/design` + `/build` cycles produce v0.1 next.**

---

## Why this exists

Free-tier offers are scattered across pricing pages, GitHub READMEs, Reddit threads, founder newsletters, and accelerator sites. They change quietly. A founder loses ~100 hours/year searching for "best free GPU this quarter" or "what credits do startups get from Cloudflare now."

This project is one continuously-updated index of those offers, with:

- **Use-case tier filter** — see only what fits a hobby project, vs. a personal site, vs. a startup MVP, vs. a production startup.
- **India-primary geographic lens** — Indian programs (Startup India, MeitY, state missions, IIT incubators) surfaced first; US / global programs accessible-from-India tagged; US-only programs in a separate tab.
- **Agentic refresh (deferred to v0.2)** — Python pipeline using free LLM providers via [LiteLLM](https://github.com/BerriAI/litellm), wrapped in an in-repo `freellm/` router that knows every free provider's quotas. Daily GitHub Actions cron + manual trigger.
- **Append-only history** — see exactly when AWS Activate's credits dropped or Vercel's free tier changed.
- **Personal-first, optionally shareable** — Render hosting, public dashboard if you want.

---

## Locked stack

| Layer | Choice |
|---|---|
| Language (backend + agents) | Python 3.11+ |
| Backend API | FastAPI |
| Frontend | Next.js 14 App Router + Tailwind + shadcn/ui (TypeScript strict) |
| LLM gateway | LiteLLM (under the hood, only imported by `freellm/`) |
| Agentic framework | **Vendor-neutral.** Default = direct LiteLLM via `freellm/`. Allowed if `/design` justifies: Pydantic AI, smolagents, LangGraph. **Banned as default**: OpenAI Agents SDK, Claude-only Agent SDK, GCP-required ADK. |
| Free-LLM router | In-repo `freellm/` sub-package — catalog + quota tracker + multimodal routing (text/vision/image-gen/video-gen/embed/STT/TTS) |
| Storage | SQLite (file, append-only) — Postgres only if Render forces it |
| Scheduler | GitHub Actions cron (daily) + manual `python -m pipeline.run` |
| Hosting | Render — FastAPI Web Service + Next.js Static Site / Web Service |
| Observability | structlog → JSON logs |

> User wrote "Light LLM" — interpreted as **LiteLLM** (BerriAI/litellm). If you meant something else, fix in [`CLAUDE.md`](./CLAUDE.md).

---

## Headline feature: use-case tier filter

Every record carries `use_case_tiers` (multi-valued, locked enum):

| Tier | Project profile |
|---|---|
| `hobby` | Weekend tinkering, learning, throwaway demos |
| `personal` | Small personal site / tool, single user, always-on |
| `startup-mvp` | Pre-revenue prototype, ~10–1000 users, easy upgrade path |
| `startup` | Paying users, production reliability, free tier as dev/sandbox only |

A record is tagged with a tier ONLY when it genuinely fits that tier. Negative criteria documented in [`provider-schema.md`](./.claude/rules/project/provider-schema.md).

## Headline feature: free-LLM router (`freellm/`)

`freellm/` is an in-repo Python sub-package (will graduate to a standalone PyPI package later). It knows every free-tier LLM / multimodal provider's quotas and routes calls in a chain so total spend stays at $0.

```python
from freellm import call_text, call_vision, call_image_gen, call_embed

result = await call_text(
    messages=[{"role": "user", "content": "Summarize this page..."}],
    task_name="extract_provider_record",
)
# result.provider_used = "groq" → "cerebras" → "gemini" → ... whichever was free + under quota
# result.cost_usd = 0.0 (always)
```

Modalities covered: text, vision, image generation, video generation, embeddings, STT, TTS. Catalog includes Groq, OpenRouter free, Together free, Cerebras, Gemini free, HF Inference, Mistral free, Replicate free, fal.ai free, Voyage free, Cohere free.

Full spec: [`.claude/rules/project/freellm-router.md`](./.claude/rules/project/freellm-router.md).

---

## Categories tracked

| Category | Examples |
|---|---|
| Cloud / hosting | AWS, GCP, Azure, Oracle, Render, Fly.io, Railway |
| GPU / AI compute | Google Colab, Kaggle, RunPod, Lambda Labs, Vast.ai, Paperspace |
| AI APIs / models | Groq, OpenRouter, Together, Cerebras, HF Inference, Replicate, Mistral |
| Databases | Supabase, Neon, MongoDB Atlas, PlanetScale, Redis Cloud |
| Storage | Cloudflare R2, Backblaze B2 |
| Auth / observability | Clerk, Auth0 free, Sentry, Logflare, Grafana Cloud free |
| **Startup credits** (India-primary) | Startup India, AWS Activate, GCP for Startups, Azure for Startups, Notion, HubSpot, Stripe Atlas |
| **Grants** (India-primary) | MeitY AI grants, state missions (KA, TS, MH), IIT/IISc incubators, NASSCOM 10000 Startups, AIM, plus US/EU programs accessible to Indian residents |
| Accelerators | YC, Techstars, Antler, regional + sectoral programs |
| OSS goldmines | Boilerplates, agent frameworks, founder tools |

Geographic priority field (`geo_priority`): `india-native | accessible-from-india | global-other | us-only | eu-only | other-region`. Default UI surfaces the first three.

---

## SHIP-TODAY scope (v0.1-seed)

3-specialist roundtable (architect + frontend + designer) cut scope to the smallest deployable demo. **Locked spec stays locked** — these are deferrals, not removals.

### What v0.1 ships

1. Hardcoded seed `data/seed.json` — 15-20 hand-curated providers.
2. FastAPI: `GET /api/providers?tier=&india=` reading the seed.
3. Next.js single page: 4 tier chips + provider grid + "Works in India" badges + parse-confidence dots + freshness labels. Dark-only.
4. Render deploy: FastAPI service + Next.js service via `render.yaml`.
5. GitHub Actions: build + lint on PR.

### What v0.2 adds

- `freellm/` router + multimodal catalog.
- Scraping collectors (`collectors/cloud/*.py`, etc.) with the ethics rule.
- Agentic pipeline (`research → extract → tier-classify → diff → verify-queue`).
- SQLite migration; append-only history.
- Daily GitHub Actions cron.
- Compare / Changes / Verify tabs.
- Slide-over (or `/provider/[slug]` route) detail view.
- Free-LLM-Chain filter mode + "Test the chain" button.
- Light/dark theme toggle.

### What v0.3+ adds — Media Generation Benchmark Dashboard

A second sub-product inside the same app. Paste a prompt → see ETA + cost + free-quota + quality across **video / image / diagram / voice / STT** providers, **ranked free-first**.

- Sub-tabs: Video gen | Image gen | Diagram gen | Voice gen | STT | Best free today | Storyboard.
- Storyboard mode auto-splits long prompts (e.g. "Explain Netflix system design with animations") into scenes, generates per-scene videos via free providers, ffmpeg-merges into one MP4. Total cost: $0 if free quotas suffice.
- Reuses the `freellm/` router — adds `estimate_cost_and_eta()` + monthly calibration agent.
- "Best free today" leaderboard ranks by quota-remaining + median ETA + quality tier.

Full spec: [`.claude/rules/project/media-benchmark.md`](./.claude/rules/project/media-benchmark.md). NOT in v0.1 scope.

Full deferred-feature list lives in [`CLAUDE.md`](./CLAUDE.md) → "SHIP-TODAY plan."

---

## Architecture (target)

```
┌────────────────────────────────────────────────────────────┐
│  Daily Agentic Pipeline (v0.2)                             │
│  GitHub Actions cron OR `python -m pipeline.run`           │
│                                                             │
│   research.py  ──▶  extractor.py  ──▶  tier_classifier.py  │
│        │                  │                    │            │
│        └────── freellm/ (LiteLLM under the hood) ──────────┤
│                Free-tier catalog + quota chain              │
│                                                             │
│   change_detector.py  ──▶  verifier.py (low-confidence)    │
└────────────────────────────────────┬───────────────────────┘
                                     │
                          append-only writes
                                     ▼
                     ┌─────────────────────────┐
                     │  SQLite (file)          │
                     │  + data/snapshots/<date>.json │
                     └────────────┬─────────────┘
                                  │
                                  ▼
                     ┌──────────────────────┐
                     │  FastAPI             │  (Render Web Service)
                     │  /api/providers      │
                     │  /api/changes        │
                     │  /api/run            │
                     │  /api/verify-queue   │
                     └────────────┬─────────┘
                                  │
                                  ▼
                     ┌──────────────────────┐
                     │  Next.js 14 + Tailwind │ (Render Static / Web Service)
                     │  + shadcn/ui            │
                     │  Tier chips, India badge,│
                     │  Free-LLM-Chain filter   │
                     └──────────────────────┘
```

---

## Repo layout (target — mostly empty until `/build`)

```
startup-resources-free/
├── api/                       # FastAPI service
├── frontend/                  # Next.js 14 App Router
├── freellm/                   # Free-LLM router library (v0.2)
├── agents/                    # LLM agents (v0.2)
├── collectors/                # Per-provider scrapers (v0.2)
├── pipeline/                  # Orchestration entry (v0.2)
├── schema/                    # Pydantic models, migrations
├── data/
│   ├── seed.json              # v0.1 hardcoded providers
│   ├── snapshots/<date>.json  # v0.2 append-only history
│   ├── raw/                   # gitignored scraped HTML
│   └── logs/
├── docs/
│   ├── plans/  architecture/  discussions/  diagrams/
│   └── design-prompt.md       # designer LLM prompt
├── tests/
├── .github/workflows/
│   ├── ci.yml                 # v0.1 — build + lint on PR
│   └── daily-pipeline.yml     # v0.2 — cron
├── .claude/rules/project/
├── render.yaml                # Render service definitions
├── pyproject.toml
├── package.json
├── CLAUDE.md
├── README.md
└── LICENSE                    # MIT
```

---

## Quick start (v0.1)

```bash
git clone git@github.com:sudhir13s/startup-resources-free.git
cd startup-resources-free

# Backend (Python 3.12 required — Render also pins to 3.12.3)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000
# Smoke test:
#   curl http://localhost:8000/api/health
#   curl http://localhost:8000/api/providers?tier=startup-mvp

# Frontend (separate terminal — Node.js 20+)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
# Open http://localhost:3000
```

## Deploy to Render (first-time setup)

1. **Connect repo** in Render dashboard → New → Blueprint → pick `sudhir13s/startup-resources-free`. Render auto-detects `render.yaml` and proposes two services: `startup-resources-api` + `startup-resources`.
2. **Before clicking deploy**, derive both public URLs from the service names:
   - API URL: `https://startup-resources-api.onrender.com`
   - Web URL: `https://startup-resources.onrender.com`
3. **Set the two `sync: false` env vars** in the Render dashboard:
   - On `startup-resources-api`: `CORS_ORIGINS=https://startup-resources.onrender.com`
   - On `startup-resources`: `BACKEND_URL=https://startup-resources-api.onrender.com`
4. Click **Deploy**. Render will build + start both services. First build ~3–5 min.
5. Free-tier services spin down after 15 min idle. First request after sleep takes ~30–60 s. Pre-warm with `curl https://startup-resources-api.onrender.com/api/health` before demoing.

> **Why this order matters:** if you deploy without `CORS_ORIGINS` + `BACKEND_URL` set, the deploy succeeds but the dashboard shows "Backend unreachable" until you add the vars and redeploy.

For v0.2 (after agentic pipeline lands):

```bash
# Optional free-LLM provider keys (any subset — missing keys are silently dropped)
cp .env.example .env
# Edit: GROQ_API_KEY, OPENROUTER_API_KEY, TOGETHER_API_KEY, CEREBRAS_API_KEY,
#       GEMINI_API_KEY, HF_TOKEN, MISTRAL_API_KEY, REPLICATE_API_TOKEN, FAL_API_KEY

# Manual pipeline run
python -m pipeline.run

# Subset
python -m pipeline.run --providers groq,vercel,supabase

# Inspect freellm catalog
python -m freellm catalog
python -m freellm plan --modality text --task-name extract-record
python -m freellm smoke-test
```

---

## Scraping ethics (non-negotiable)

This project scrapes public free-tier pages. Strict rules apply, full text in [`scraping-ethics.md`](./.claude/rules/project/scraping-ethics.md):

- robots.txt + ToS reviewed per collector, link in header.
- Honest, identifiable User-Agent.
- ≤ 1 request / 30s per host.
- Weekly cadence default; daily only via official APIs.
- ETag / Last-Modified caching.
- Takedown requests honored same-day.

---

## Conventions

- **Append-only history.** No record updated in place. New scrape = new row.
- **Free-LLM only.** No paid LLM calls without explicit `LLM_ALLOW_PAID=1`.
- **Vendor-neutral agentic stack.** No vendor-specific agent SDK as default.
- **No AI attribution** in commits, PRs, or code.
- **Search first** — grep the repo before adding code or collectors.
- **No placeholders** — `// TODO`, stubs, or "not implemented" don't merge.
- **Dated artifacts.** Every plan / architecture / discussion lives at `docs/<topic>/<slug>/<YYYY-MM-DD>T<HH-MM>-<short-name>.md`. Append-only.

---

## Documents

- [`project-idea.md`](./project-idea.md) — original brainstorm
- [`CLAUDE.md`](./CLAUDE.md) — project router for AI tooling, with SHIP-TODAY plan
- [`docs/design-prompt.md`](./docs/design-prompt.md) — paste into v0.dev / Lovable / Galileo / Figma AI / designer LLM
- [`.claude/rules/project/provider-schema.md`](./.claude/rules/project/provider-schema.md) — canonical record shape, GEO + USE_CASE_TIER rubrics
- [`.claude/rules/project/scraping-ethics.md`](./.claude/rules/project/scraping-ethics.md) — collector rules
- [`.claude/rules/project/agentic-pipeline.md`](./.claude/rules/project/agentic-pipeline.md) — LiteLLM + agent rules + vendor-neutrality policy
- [`.claude/rules/project/freellm-router.md`](./.claude/rules/project/freellm-router.md) — `freellm/` library spec

---

## License

MIT for code. CC-BY-4.0 proposed for data snapshots — confirm before public release.
