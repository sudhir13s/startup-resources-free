# Ship-Today Roundtable — 2026-04-26 ~12:00 IST

> **Purpose:** Cut the locked v1 spec down to a basic-but-deployed v0.1 ship-target inside a 2-hour window. User mandate: build + deploy on Render today.
>
> **Specialists dispatched (parallel):** System Architect, Frontend Engineer, Product Designer, DevOps/MLOps.
>
> **Outcome:** v0.1-seed scope locked into `CLAUDE.md` → "SHIP-TODAY plan." Original v1 spec stays locked elsewhere — these are deferrals, not removals.

## Files

- [`architect.md`](./architect.md)
- [`frontend.md`](./frontend.md)
- [`designer.md`](./designer.md)
- [`devops.md`](./devops.md)

## Convergent findings (3-of-4 specialists)

| Theme | Cuts converged on by | Confidence |
|---|---|---|
| Defer agentic pipeline + LiteLLM router + scrapers + cron | Architect | 9-10 |
| Defer SQLite — use static JSON seed | Architect | 9 |
| Defer Compare / Changes / Verify tabs (render disabled stubs in nav) | Architect, Frontend, Designer | 7-9 |
| Defer slide-over panel | Frontend, Designer | 7 |
| Defer Free-LLM-Chain filter (no router exists yet) | Frontend, Designer | 7 |
| Defer category multi-select | Frontend | 6 |
| Defer dark-mode toggle — ship dark-only | Frontend, Designer | 5-7 |
| `india_accessible: bool` flag in seed → "Works in India" badge on cards | Architect, Designer | 5-6 |
| Skeleton loading states required | Designer | 8 |
| Tier chip "hobby" pre-selected on first paint | Designer | 9 |

## DevOps-specific (solo, confidence 9)

- Next.js MUST be Web Service, NOT Static Site (server components / route handlers).
- Free-tier Render services don't share private network → frontend calls API via public Render URL.
- Env-var circular dependency: name both services in `render.yaml` first, derive URLs as `https://<name>.onrender.com`, set `BACKEND_URL` + `CORS_ORIGINS` in Render dashboard BEFORE first deploy.
- Pin Python 3.12.3 + Node 20.12.2 explicitly.

## Solo findings (kept)

- Inline expanded card for detail (Frontend) vs `/provider/[slug]` route (Designer): chose inline for time, route in v0.2.
- Designer R3: India context as **badge on cards** not page-level filter (avoids empty-state multiplication).
- Architect O2: Render cold-start ~30-60 s — document in README.

## Top 3 risks

1. **Env-var circular dependency** between Render services. Mitigation: derive URLs from service names before deploy.
2. **Cold start UX** on free Render. Mitigation: warm-curl ping before demo + README note.
3. **Time overrun** if shadcn init or render.yaml debugging eats > 25 min. Mitigation: stop at 25-min mark and reassess.

## Assigned action

Implement in order:
1. Q&A with user (5 min) — GitHub repo + Render account confirmation.
2. Repo scaffold (Next.js + FastAPI + shadcn init) — 25 min.
3. Seed data + FastAPI route — 15 min.
4. Next.js components + page — 50 min.
5. Render setup + deploy + smoke test — 25 min.
6. README + commit + push — 10 min.

Total target: ~130 min.
