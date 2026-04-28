# ResourceOS

A dashboard that aggregates **free / discounted / time-limited** offerings — cloud, GPUs, AI APIs, databases, hosting, startup credits, grants, accelerators — and ranks them by project stage. India-primary.

**Live**: <https://startup-resources.onrender.com>

**API health**: <https://startup-resources-api.onrender.com/api/health>

51 curated providers · 6 use-case tiers · daily cron · append-only history.

---

## Tabs

| Tab | What |
|---|---|
| **Catalog** | All providers. Filters: tier, region, category, offer-type, parse-confidence. |
| **Grants & Credits** | Filtered to grants / credits / accelerators / perks. India-accessible toggle. |
| **Compare** | Pin up to 6 providers, side-by-side. Diffing cells highlighted. |
| **Changes** | Reverse-chronological field-level diffs between snapshots. |
| **Verify** | Low-confidence extractor outputs awaiting human review (y/n shortcuts). |
| **Free-LLM Chain** | Visualizes the quota-aware fallback chain across free LLM providers. |

---

## Run locally

```bash
git clone git@github.com:sudhir13s/startup-resources-free.git
cd startup-resources-free

# Backend (FastAPI on :8000)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal — Node 20+)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
# Open http://localhost:3000
```

### Optional — full agent stack (LLM extraction)

```bash
pip install -r backend/requirements-agents.txt
omniroutectl env-sync && omniroutectl up    # boots OmniRoute via Docker
python -m pipeline --mode auto --providers groq,vercel,render --rate-limit-s 5
```

Free-provider keys (`GROQ_API_KEY`, `GEMINI_API_KEY`, `HF_TOKEN`, etc.) read from your shell env.

---

## Deploy to Render

```
New → Blueprint → sudhir13s/startup-resources-free → Deploy
```

Render auto-detects [`render.yaml`](./render.yaml). Two services come up:

- API: `https://startup-resources-api.onrender.com`
- Web: `https://startup-resources.onrender.com`

CORS + backend URL wiring auto-derives via `fromService` — no manual env entry. Free-tier services spin down after 15 min idle (~30–60 s cold start).

---

## Daily cron

`.github/workflows/daily-pipeline.yml` runs at 02:00 UTC + jitter, plus manual dispatch:

```bash
gh workflow run daily-pipeline.yml \
  --repo sudhir13s/startup-resources-free \
  -f mode=auto \
  -f providers=groq,vercel,render
```

Modes: `heuristic` (no LLM, default) · `auto` (LLM with per-provider fallback) · `llm` (LLM-only, fail loud).

When the run produces deltas, the bot commits `data/snapshots/<date>.json` + `data/resourceos.db` to main. Render auto-redeploys.

---

## Stack

Python 3.12 + FastAPI + SQLite · Next.js 14 + Tailwind + shadcn/ui · Render · GitHub Actions cron · in-repo `freellm/` router over OmniRoute proxy.

---

## Internal docs

For maintainers — not needed to use the dashboard:

- [`CLAUDE.md`](./CLAUDE.md) — project rules for AI tooling
- [`project-idea.md`](./project-idea.md) — original brainstorm
- [`.claude/rules/project/`](./.claude/rules/project/) — provider schema, scraping ethics, agent rules, freellm spec, hosting migration plan

---

## License

MIT.
