# architect — 2026-04-26 ~12:00 IST

[PERSONA: architect | confidence: see per-finding]

## Blockers (cut these or ship fails)

- **[1] Agentic pipeline + LiteLLM router** — confidence 10/10. Source: Google SWE Book — complexity budget. Each absorbs 2 hours alone. Cut completely. Catalog works without them.
- **[2] SQLite + schema migrations** — confidence 9/10. Source: 12-Factor §IV. SQLAlchemy + Alembic + Render ephemeral disk = 30-45 min plumbing. Cut. Read static JSON.
- **[3] GitHub Actions cron scraper** — confidence 9/10. Source: 12-Factor §IX. No scraper = no cron. JSON seed IS the data layer.
- **[4] Compare, Changes, Verify tabs** — confidence 9/10. Cut to one tab: Catalog. Tab labels render disabled in nav.

## Recommendations

- **[5] shadcn full setup** — confidence 7/10. Source: Airbnb JS Guide. CLI/config friction. Use plain Tailwind chips/cards. (Frontend disagreed; final: install only `card`, `button`, `badge`.)
- **[6] Free-LLM-Chain filter** — confidence 7/10. No router exists. Render disabled stub max.

## Observations

- **[7] India geo via `india_accessible: bool`** — confidence 5/10. Sufficient for v0.1; no IP detection.
- **[8] Render cold-start** — confidence 4/10. Free-tier spin-down. Document.

## Assigned action

Ship: `data/seed.json` (15-20) + FastAPI 1 route + Next.js 1 page (4 chips + grid) + render.yaml.
