# Project Rule: Scraping Ethics + Resilience

> Binds `refresh/fetch.py` and every extraction step that fetches data from a third-party site. Goal: legal, polite, durable. Getting us banned is worse than no fetch at all.

## Hard prohibitions

- No scraping behind auth walls or paywalls.
- No bypassing `robots.txt`. If `Disallow:` covers the path, do not fetch.
- No spoofing User-Agent to evade rate limits or WAFs.
- No headless-browser fingerprint randomization for the purpose of evasion.
- No hammering: never default to faster than 1 request / 30 seconds per host.
- No re-fetch of unchanged pages within the same week (cache + ETag/Last-Modified).
- No commit of scraped HTML/JSON snapshots that contain copyrighted prose verbatim. Extract structured fields only.
- No fetch for any provider listed in `BLOCKLIST.md` (created on first takedown request).

## Required for every new provider's `source_urls`

A provider is not ready for refresh until:

1. **Source-of-truth choice in this order:**
   1. Official API (e.g. AWS Pricing API, GCP Billing Catalog) — strongly preferred.
   2. Official RSS / changelog / status feed.
   3. Documented public JSON endpoint.
   4. HTML fetch (`refresh/fetch.py`, with the Jina Reader fallback) — last resort.
2. **`robots.txt` + ToS reviewed** — `PoliteFetcher` checks robots.txt per host at fetch time;
   note the review date if the provider needed a manual exception discussion.
3. **Polite client config (already enforced by `refresh/fetch.py` — do not weaken it):**
   - `USER_AGENT = "ResourceOS/2.0 (+https://github.com/sudhir13s/startup-resources-free)"`.
   - Default rate: 1 request per 30 s per host (`DEFAULT_MIN_INTERVAL_S`).
   - Timeout 30 s (`DEFAULT_TIMEOUT_S`). Retry max 2, backoff with jitter, only on
     408/429/500/502/503/504 — never on other 4xx. `Retry-After` honored exactly.
4. **Caching:** ETag / Last-Modified conditional GET via the repository's `"http-cache"` state
   namespace (not a local file cache) — a 304 skips body parsing and the LLM call entirely.
5. **Idempotent, versioned writes:** `storage/` appends a new version on an accepted change;
   re-running against an unchanged page writes nothing (the hash gate, see `agentic-pipeline.md`).
6. **Freshness timestamp** on every record (`scraped_at`, ISO 8601, UTC).
7. **Source URLs** stored verbatim in `source_urls` so a human can verify.
8. **Confidence score** on the record: `high` / `medium` / `low` (`parse_confidence`). The UI
   surfaces `low` on the Changes and Candidates pages.
9. **Diff-aware persistence:** `refresh/merge.py`'s never-degrade merge only stores a new
   version when something changed; a no-op run touches nothing.
10. **Failure mode:** on fetch or parse failure, emit a structured log entry with the reason —
    never silently drop a provider from the run.

## Stop conditions (pause the provider immediately)

- HTTP 403 / 429 sustained over 3 runs → pause that provider's `source_urls`, alert the user.
- Provider sends a takedown / cease-and-desist (email, GitHub issue, abuse contact) → add to `BLOCKLIST.md` SAME DAY, mark all existing records `source_method: manual`, do NOT delete history.
- robots.txt changes to `Disallow:` for our path → stop, don't grandfather in.
- Schema drift breaks extraction → stop emitting for that provider (don't write garbage); the
  record falls back to `parse_confidence: low` rather than crashing the whole run.

## Concurrency + politeness

- Per-host concurrency: 1. Never two parallel requests to the same host.
- Cross-host concurrency: cap at `MAX_CONCURRENT_HOSTS = 5` hosts in flight (`refresh/fetch.py`)
  — a run triggered on the same Render process the API runs in can't reasonably do more.
- No schedule to jitter against: refresh is button-triggered, not cron (see `agentic-pipeline.md`
  and the Stack table in `CLAUDE.md`), so there is no "top of the hour" collision to avoid.

## Storage rules for fetched data

- Parsed records → SQLite (`storage/sqlite_repository.py`), version-controlled on the dedicated
  `data` git branch, not `main` (`storage/github_sync.py`).
- History is append-only. NEVER overwrite a previous row. Every accepted change is a new
  version; latest-by-`provider_id` is a query, not a mutation.
- Fetched page text is not persisted as files — only its hash (for the hash gate) and, when a
  change is accepted, the extracted record. There is no committed weekly snapshot; the `data`
  branch's git history over `resourceos.db` is the public-readable timeline.

## Legal posture (read once, internalize)

- Scraping public-tier pages is generally legal in the US (hiQ v. LinkedIn, 9th Cir.) but ToS violation can still trigger civil action.
- We're personal-scale. Keep it that way: low volume, identifiable UA, easy-to-honor takedowns. Don't pretend to be a search engine.
- If this project ever gets monetized (`FreeStackHub.com` angle from `project-idea.md`), revisit this rule. Commercial use changes the calculus.

## What this rule does NOT prevent

- Reading provider docs as a human (open in browser, copy-paste a free-tier limit). That's not scraping.
- Using official affiliate / partner programs that explicitly authorize automated catalog access.
- Calling LLM APIs against provider docs (we are the user of OpenRouter / Groq, not scraping them).

## Self-check before adding a new provider's `source_urls`

- [ ] robots.txt + ToS reviewed within the last 30 days.
- [ ] Source-of-truth preference followed (official API before HTML fetch).
- [ ] Rate limit ≤ 1 req/30s/host (unchanged in `refresh/fetch.py` — no per-provider override).
- [ ] ETag / Last-Modified caching in effect (automatic via `PoliteFetcher`).
- [ ] Failure path emits a structured log entry (no silent drop).
- [ ] Schema drift detection: extraction falls back to `parse_confidence: low` instead of crashing.
- [ ] Record carries: `provider_id`, `category`, `scraped_at`, `source_urls`, `parse_confidence`.
- [ ] BLOCKLIST.md checked.
- [ ] No copyrighted prose committed verbatim to the repo.

If any box is unchecked, don't add the provider's `source_urls` yet.
