# frontend — 2026-04-26 ~12:00 IST

[PERSONA: frontend | confidence: see per-finding]

## Blockers

- **B1 — `/api/providers` route doesn't exist** — confidence 9/10. Hard prereq before component work.
- **B2 — Next.js project doesn't exist** — confidence 9/10. `create-next-app --typescript --tailwind --app` first 10 min, then shadcn init.

## Recommendations

- **R1 — Defer all tabs except Catalog** — confidence 7/10. Render disabled stubs.
- **R2 — Defer slide-over panel** — confidence 7/10. Radix Sheet/Dialog ~40 min wiring. Inline expand instead.
- **R3 — Defer dark mode toggle** — confidence 7/10. `next-themes` 20 min. Ship dark-only.
- **R4 — Drop Free-LLM-Chain filter from v0.1 entirely** — confidence 7/10. Router data doesn't exist.
- **R5 — Defer category multi-select** — confidence 6/10. Tier chips alone prove differentiator.

## Observations

- **O1 — Parse-confidence badge** — confidence 5/10. shadcn Badge variant, 5 min, high signal. Keep.
- **O2 — Freshness badge** — confidence 5/10. `Intl.RelativeTimeFormat`. Keep.

## Assigned action

Ship in order:
1. `app/page.tsx` (single route)
2. `app/api/providers/route.ts` (static JSON pass-through)
3. `components/TierFilterChips.tsx` (4 shadcn Button-variant toggle chips, URL-param driven)
4. `components/ProviderCard.tsx` (Card + Badge for parse-confidence + Badge for freshness)
5. `components/ProviderGrid.tsx` (CSS grid wrapper)
6. Wire in `app/page.tsx` — Server Component fetches `/api/providers`, filters by tier, passes array.

shadcn components: `card`, `button`, `badge`. Nothing else.
