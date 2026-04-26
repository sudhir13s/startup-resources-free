# Project Rule: Scraping Ethics + Resilience

> Binds every collector / extractor / agent that fetches data from a third-party site. Goal: legal, polite, durable. A collector that gets us banned is worse than no collector.

## Hard prohibitions

- No scraping behind auth walls or paywalls.
- No bypassing `robots.txt`. If `Disallow:` covers the path, do not fetch.
- No spoofing User-Agent to evade rate limits or WAFs.
- No headless-browser fingerprint randomization for the purpose of evasion.
- No hammering: never default to faster than 1 request / 30 seconds per host.
- No re-fetch of unchanged pages within the same week (cache + ETag/Last-Modified).
- No commit of scraped HTML/JSON snapshots that contain copyrighted prose verbatim. Extract structured fields only.
- No collector for any provider listed in `BLOCKLIST.md` (created on first takedown request).

## Required for every new collector

A collector PR is incomplete until it has:

1. **Source-of-truth choice in this order:**
   1. Official API (e.g. AWS Pricing API, GCP Billing Catalog) — strongly preferred.
   2. Official RSS / changelog / status feed.
   3. Documented public JSON endpoint.
   4. HTML scraping — last resort.
2. **`robots.txt` + ToS link** in the collector header comment (date-stamped).
3. **Polite client config:**
   - Real `User-Agent`: `startup-resources-free/<version> (+https://github.com/<user>/startup-resources-free; contact: <email>)`.
   - Default rate: 1 req per 30 s per host. Override only with documented justification.
   - Default cadence: weekly. Daily only if the provider's offer changes that often AND the source is an API (not HTML).
   - Timeout: 30 s. Retry: max 2, exponential backoff with jitter, NO retry on 4xx (except 408/429).
   - Honor `Retry-After` exactly.
4. **Caching layer:** ETag / Last-Modified / If-Modified-Since. Skip body parse on 304.
5. **Idempotent writes:** writing the same record twice produces the same row (upsert by `(provider_id, scraped_at_date)` not by autoincrement).
6. **Freshness timestamp** on every record (`scraped_at`, ISO 8601, UTC).
7. **Source URL** stored verbatim per record so a human can verify.
8. **Confidence score** per field: `high` (from API), `medium` (from structured HTML), `low` (regex-on-prose). UI must surface this.
9. **Diff-aware logging:** log only when a field changed vs. previous run. No-change runs log a single line.
10. **Failure mode:** on parse failure, save raw response under `data/raw/<provider>/<date>.html` (gitignored) and emit a structured log entry — never silently drop.

## Stop conditions (kill the collector immediately)

- HTTP 403 / 429 sustained over 3 runs → pause collector, alert user.
- Provider sends a takedown / cease-and-desist (email, GitHub issue, abuse contact) → add to `BLOCKLIST.md` SAME DAY, mark all existing records `source: manual`, do NOT delete history.
- robots.txt changes to `Disallow:` for our path → stop, don't grandfather in.
- Schema drift breaks the parser → stop emitting (don't write garbage), open a TODOS.md task to update the parser.

## Concurrency + politeness

- Per-host concurrency: 1. Never two parallel requests to the same host.
- Cross-host concurrency: cap at 5 hosts in flight (a single GitHub Actions runner can't reasonably do more without flaking).
- Random jitter on schedule (±10 minutes from the cron baseline) so we don't hit every provider at the top of the hour with everyone else.

## Storage rules for scraped data

- Raw responses → `data/raw/<provider>/<YYYY-MM-DD>.{html,json}` — gitignored except a tiny fixture set in `data/raw/_fixtures/` for tests.
- Parsed records → DB (Supabase / SQLite — pending stack lock).
- History is append-only. NEVER overwrite a previous row. New scrape = new row. Latest-by-`(provider_id)` is a query, not a mutation.
- A small JSON snapshot (`data/snapshots/<YYYY-MM-DD>.json`) is committed weekly so the repo itself carries a public-readable timeline.

## Legal posture (read once, internalize)

- Scraping public-tier pages is generally legal in the US (hiQ v. LinkedIn, 9th Cir.) but ToS violation can still trigger civil action.
- We're personal-scale. Keep it that way: low volume, identifiable UA, easy-to-honor takedowns. Don't pretend to be a search engine.
- If this project ever gets monetized (`FreeStackHub.com` angle from `project-idea.md`), revisit this rule. Commercial use changes the calculus.

## What this rule does NOT prevent

- Reading provider docs as a human (open in browser, copy-paste a free-tier limit). That's not scraping.
- Using official affiliate / partner programs that explicitly authorize automated catalog access.
- Calling LLM APIs against provider docs (we are the user of OpenRouter / Groq, not scraping them).

## Self-check before merging any collector

- [ ] robots.txt + ToS reviewed within the last 30 days, link in header.
- [ ] User-Agent is honest and identifiable.
- [ ] Rate limit ≤ 1 req/30s/host.
- [ ] Cadence ≤ weekly (or justified daily via API).
- [ ] ETag / Last-Modified caching wired.
- [ ] Failure path saves raw + emits structured log (no silent drop).
- [ ] Schema drift detection: collector emits `parse_confidence: low` instead of crashing.
- [ ] Records carry: `provider_id`, `category`, `scraped_at`, `source_url`, `parse_confidence`.
- [ ] BLOCKLIST.md checked.
- [ ] No copyrighted prose committed verbatim to the repo.

If any box is unchecked, the collector doesn't merge.
