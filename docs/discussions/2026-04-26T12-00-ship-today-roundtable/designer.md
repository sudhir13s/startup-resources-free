# designer — 2026-04-26 ~12:00 IST

[PERSONA: designer | confidence: see per-finding]

## Blockers

- **B1 — Tier chip filter must work on first render** — confidence 9/10. `hobby` pre-selected by default. Empty grid below unselected chips reads as broken.
- **B2 — No empty-white loading state** — confidence 8/10. Render cold-start ~800ms-30s. Skeleton pulse cards required.
- **B3 — 4.5:1 body-text contrast verified before ship** — confidence 8/10. `#0f172a` slate-900 bg + white body. Gray-on-gray subtitles are the failure point.

## Recommendations

- **R1 — One tab visible (Catalog), three muted "Coming soon"** — confidence 7/10. One working tab > four broken.
- **R2 — Above-fold = name + 1-line value prop + 4 chips, nothing else** — confidence 7/10. Chips ARE the hero.
- **R3 — India context as badge on cards, not page filter** — confidence 6/10. "Works in India" microcopy (warmer than "Indian residents").
- **R4 — Card anatomy: 5 fields max** — confidence 7/10. Logo/name + tier + 3 limits + India badge. Slide-over → static `/provider/[slug]` route. (Frontend pushed back; final: inline expand for v0.1, route in v0.2.)

## Observations

- **O1 — Dark default for dev audience** — confidence 5/10. Toggle in nav OR dark-only OK.
- **O2 — Free-LLM-Chain is v1.1+** — confidence 5/10. Most novel but most complex empty state.
- **O3 — Mobile: 1-col grid, chips horizontal-scroll** — confidence 4/10. `overflow-x: auto` on chip row.

## Assigned action

Single page render:
- Top nav: logo + "Dark mode" toggle (or dark-only).
- Below: 1 sentence value prop in 24px white.
- Below: horizontal pill row — 4 tier chips with distinct accent per chip (hobby pre-selected, filled).
- Below: responsive card grid (1/2/3-col).
- Cards: logo, name, tier label, 3 key limits, "Works in India" badge if applicable.
- Cards link to `/provider/[slug]` static page (downgraded to inline-expand in final scope).
- Loading: skeleton pulse cards.
- Empty: "No free tiers for this stage yet — add one" + GitHub link.
- Compare/Changes/Verify in nav: muted, "Coming soon" tooltip.
- Animations: skeleton pulse only.
