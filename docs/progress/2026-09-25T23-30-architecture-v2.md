---
type: progress
title: Architecture v2 — modular core, on-demand refresh, SQLite-in-git
slug: architecture-v2
status: done
created: 2026-09-25T23-30
revises: null
source: docs/plans/architecture-v2/2026-09-25T20-44-modular-refresh-rebuild.md
tasks: [AV2-0, AV2-1, AV2-2, AV2-3, AV2-4, AV2-5, AV2-6, AV2-7]
milestone: M[av2]
---

## 2026-09-25

### Completed

- **AV2-0 — contracts.** `domain/` package: `ProviderRecord` v2 (`records.py`), taxonomy enums
  (`taxonomy.py`), filters/facets (`filters.py`), field-level change model (`changes.py`), run
  and candidate/verify models (`runs.py`). — [PR #61](https://github.com/sudhir13s/startup-resources-free/pull/61)
- **AV2-1 — storage.** `storage/` package: the `Repository` protocol, `SqliteRepository`,
  numbered schema migrations, seed import, and `github_sync.py` for the `data`-branch
  pull/push. — [PR #65](https://github.com/sudhir13s/startup-resources-free/pull/65)
- **AV2-2 — freellm.** Rebuilt `freellm/` on a plain OpenAI-compatible `httpx` backend
  (`freellm/backend.py`), dropping the LiteLLM/OmniRoute-sidecar design so the service fits
  Render's 512 MB free instance; quota and cooldown state now flow through an injected
  `StateStore` rather than a fixed on-disk path. — [PR #62](https://github.com/sudhir13s/startup-resources-free/pull/62);
  GitHub Models removed from the free catalog after it was retired upstream —
  [PR #68](https://github.com/sudhir13s/startup-resources-free/pull/68)
- **AV2-3 — frontend.** Service-aware category filters with live facet counts, a sectioned
  provider detail dialog, and the Refresh button / Runs / Candidates / Changes pages with
  passphrase-gated admin session routes. — [PR #64](https://github.com/sudhir13s/startup-resources-free/pull/64),
  [PR #63](https://github.com/sudhir13s/startup-resources-free/pull/63)
- **AV2-4 — data.** New v2 provider catalog: 74 curated records in
  `data/providers_seed.json`, each broken into `services[]` with per-service category and
  limits. — [PR #66](https://github.com/sudhir13s/startup-resources-free/pull/66); a
  validation gap in how serialized derived fields were re-accepted was fixed the same day —
  [PR #67](https://github.com/sudhir13s/startup-resources-free/pull/67)
- **AV2-5 / AV2-6 — refresh pipeline + API.** `refresh/` package: polite fetch with robots.txt
  and a 30-second-per-host rate limit, a page-hash gate that skips the LLM call when a source
  page is unchanged, free-LLM structured extraction, a never-degrade merge into new record
  versions, and discovery of new candidate providers through a quota-rotated search chain
  (Tavily → Exa → Jina → Linkup → SerpAPI). `api/` was rebuilt as a repository-backed FastAPI
  service with routers for providers (with facets), provider detail, changes, runs, refresh
  start/status, and candidate approve/reject; admin write endpoints require `X-Admin-Token`;
  the app pulls the database from the `data` branch on boot, migrates it, and imports any seed
  rows not yet present. — [PR #69](https://github.com/sudhir13s/startup-resources-free/pull/69),
  [PR #76](https://github.com/sudhir13s/startup-resources-free/pull/76)
- **AV2-7 — retire the old pipeline, sync docs.** Removed `backend/`, `agents/`, `collectors/`,
  `pipeline/`, `schema/`, `scripts/`, `data/seed.json`, `data/snapshots/`,
  `data/refresh_runs/`, the committed `data/resourceos.db`, the daily-pipeline / weekly-refresh
  / weekly-discovery / manual-full-run GitHub Actions workflows, and the Media Benchmark page
  stub. Updated README, CLAUDE.md, `.env.example`, and every `.claude/rules/project/*.md` file
  to describe the v2 layout instead of the retired one (this document).

### Changes

- **Removed** (all merged to `main` across the PRs above): `backend/`, `agents/`,
  `collectors/`, `pipeline/`, `schema/`, `scripts/`, `data/seed.json`, `data/snapshots/`,
  `data/refresh_runs/`, the committed `data/resourceos.db`, `.github/workflows/daily-pipeline.yml`,
  `.github/workflows/weekly-refresh.yml`, `.github/workflows/weekly-discovery.yml`,
  `.github/workflows/manual-full-run.yml`, and the Media Benchmark page stub under `frontend/`.
- **Added**: `domain/`, `storage/`, `refresh/`, and a rebuilt `api/` and `freellm/` at the repo
  root (no `backend/` subdirectory); `data/providers_seed.json` (74 v2 records) replacing
  `data/seed.json`.
- **Docs synced in this change**: `README.md` (quick start, architecture overview with a
  Mermaid diagram, how refresh works, Render env var tables), `CLAUDE.md` (stack table,
  project structure, dashboard section; removed the stale SHIP-TODAY plan, "Repo state
  (2026-04-26)", "What is DEFERRED", and the v0.1 release checklist — all superseded by this
  progress history and the architecture-v2 plan), `.env.example` (every current env var,
  grouped, no OmniRoute/stale entries), and every `.claude/rules/project/*.md` file (path and
  concept references updated: `agents/`→`refresh/`, `schema/records.py`→`domain/records.py`,
  `pipeline/`→`refresh/runner.py`, GitHub Actions cron/snapshots→button-triggered + `data`
  branch, OmniRoute/LiteLLM-only→freellm's OpenAI-compatible backend, and the provider record
  schema section rewritten for the v2 `services[]`/`credits[]`/`claim_steps`/`links` shape).

### Decisions (+why)

- **SQLite persisted on a dedicated `data` git branch, not `main`.** A refresh run only ever
  touches the `data` branch, so accepting or rejecting a candidate never triggers a Render
  redeploy or a CI run on `main` — the two concerns (code changes, data changes) stay on
  separate branches with separate cadences.
- **Refresh runs inside the Render API process on button click only — no cron.** The earlier
  design ran a daily GitHub Actions pipeline; this rebuild replaces it because a personal-scale
  catalog doesn't need daily freshness, and an in-process run is simpler to observe (the Runs
  page shows live status) and cheaper to operate than a scheduled workflow plus a commit-back
  step.
- **A plain OpenAI-compatible `httpx` backend instead of LiteLLM.** LiteLLM's dependency
  footprint didn't reliably fit Render's 512 MB free instance alongside FastAPI and Pydantic.
  `freellm/` keeps its curated catalog, quota tracking, and modality-aware routing — only the
  HTTP client underneath changed. LiteLLM remains fine for local experimentation; it is not a
  runtime dependency of anything deployed.
- **GitHub Models removed from the free catalog.** The provider was retired upstream on
  2026-07-30; keeping it in the catalog would have surfaced a chain entry that always fails.
- **`data/providers_seed.json` doubles as a hand-correction channel.** `storage/seed_import.py`
  re-applies a seed entry whose content changed since it was last imported (diffed on the
  Changes page like any other change), while leaving an unchanged entry alone so it never
  overwrites what a refresh has since learned. This means a wrong number can be fixed by
  editing the seed file and deploying, without needing a live refresh run.

### Backlog

- Checked off: `M[av2] - Architecture v2: modular core, on-demand refresh, SQLite-in-git` and
  `AV2-0` through `AV2-7` (all folded into this entry; removed from `BACKLOG.md`'s pending
  sections since their record now lives here).
- Left **in progress**: `AV2-8 Render env setup + live refresh smoke test` — a user action
  (setting the Render dashboard secrets and confirming a live refresh run) not something an
  agent can complete unattended.
- Added to **Next**: re-verify unverified catalog records (ai-api, credits, grants); triage
  the open Dependabot PRs that still reference the pre-move `backend/` directory.

## Known gaps

- **Oracle Cloud's free-tier page could not be verified** during the AV2-4 seed pass — the
  page blocked the fetch; its record in `data/providers_seed.json` should be treated as
  lower-confidence until a manual check-through.
- **Several catalog records remain unverified** past their initial curation pass — see the
  `Next` backlog item above.
- **Refresh has not yet been run live in production.** AV2-8 (Render env setup) is the
  remaining step; until it completes, the deployed catalog is seed-only.
- **The `data` git branch does not exist yet.** It is created automatically on the first
  successful refresh run (`storage/github_sync.py` pushes to it); until then, the API falls
  back to seed-only persistence with a logged warning on each boot.
