# Project Rule: Provider Record Schema

> The canonical shape of a "provider offering" record. Every collector emits this shape. Every UI/API consumes this shape. Schema changes are migrations, not silent edits.

## Why a fixed schema

`project-idea.md` lists 7+ categories (cloud, GPU, AI APIs, DBs, credits, grants, OSS). Tempting to give each category its own schema. Don't. A single normalized shape makes:

- Cross-category ranking ("best free stack for AI app") trivial.
- The dashboard one component instead of seven.
- History diffs comparable across providers.

## The shape (canonical — don't drift)

```jsonc
{
  // Identity (required, immutable per record)
  "id": "uuid",                         // generated; stable across re-scrapes
  "provider_id": "groq",                // slug, stable, unique within a category
  "provider_name": "Groq",              // display name, vendor-cased
  "category": "ai-api",                 // enum (see CATEGORY_ENUM below)
  "subcategory": "llm-inference",       // optional refinement
  "source_url": "https://groq.com/...", // exact URL the data came from

  // The offering (the actual signal)
  "offer_type": "free-tier",            // enum: free-tier, free-credits, free-trial, free-quota, grant, perk, oss
  "offer_summary": "Free LLM inference up to N requests/day",
  "currency": "USD",                    // ISO 4217; null for non-monetary offers
  "credit_amount": null,                // numeric, in `currency`; null if N/A
  "credit_duration_days": null,         // 365 for "free for a year"; null for always-free or one-time

  // Limits (free-form key/value because shape varies wildly)
  "limits": {
    "requests_per_day": 14400,
    "tokens_per_minute": 30000,
    "models": ["llama-3.1-70b", "mixtral-8x7b"]
  },

  // Eligibility + access
  "access_method": "api-key",           // enum: api-key, oauth, signup, email-verify, github-auth, manual-apply, invite-only
  "eligibility": {
    "regions": ["global"],              // ISO country codes or "global"
    "user_types": ["any"],              // any, student, startup, founder, researcher, oss-maintainer, india-resident, etc.
    "company_age_max_years": null,      // for startup credits
    "funding_max_usd": null             // for startup credits
  },
  "restrictions": "Personal use only. Commercial use requires paid plan.",

  // Geographic priority (LOCKED enum — India-primary; drives default sort)
  "geo_priority": "accessible-from-india",
  // ^ One of: india-native | accessible-from-india | global-other | us-only | eu-only | other-region
  // See "GEO_PRIORITY rubric" below.

  // Use-case fit (locked 6-tier enum — drives the dashboard tier filter)
  "use_case_tiers": ["hobby", "personal", "startup-mvp", "pre-seed"],
  // ^ Multi-valued. A provider "fits" a tier when its free offer is sufficient + safe to use at that stage.
  // See "Use-case tier rubric" below for how to assign these. Set by collector heuristic; overridable by user.

  "tier_fit_rationale": "Free quota fits hobby + personal; startup-mvp possible if user count under 1k/day; not safe for revenue-bearing startup workloads (rate caps).",

  // Quality / freshness signals
  "scraped_at": "2026-04-26T11:47:00Z", // UTC ISO 8601, REQUIRED on every record
  "parse_confidence": "high",           // high | medium | low — see scraping-ethics.md
  "source_method": "api",               // api | rss | structured-html | regex-html | manual
  "last_verified_at": "2026-04-26",     // date a human (or robust API) confirmed; may be older than scraped_at
  "expiry_date": null,                  // when the offer ends; null = ongoing

  // Status + history pointers
  "status": "active",                   // active | reduced | ended | unknown
  "supersedes_id": null,                // points to previous record id when this is an update
  "notes": "Provider rebranded from foo to bar on 2026-03-01."
}
```

## CATEGORY_ENUM (lock these slugs — don't invent variants)

```
cloud           — IaaS / PaaS / hosting platforms (AWS, GCP, Vercel, Fly)
gpu             — GPU compute (Colab, RunPod, Lambda)
ai-api          — hosted model inference (Groq, OpenRouter, HF Inference)
database        — managed DB (Supabase, Neon, Mongo Atlas)
storage         — object / blob storage (R2, B2)
auth            — managed auth (Clerk, Auth0, Supabase Auth)
observability   — logs / metrics / errors (Grafana Cloud, Sentry, Logflare)
domain          — domains / DNS / email
startup-credit  — bundled credits (AWS Activate, GCP for Startups, Azure for Startups)
grant           — non-dilutive funding (govt, foundation, sector-specific)
accelerator     — accelerator / incubator programs
perk            — SaaS discount (Notion, HubSpot, Stripe Atlas)
oss             — useful open-source repo (template, framework, tool)
learning        — free course / cert / paper feed
```

If you need a new slug, add it here AND migrate existing records. Don't sprinkle ad-hoc slugs.

## GEO_PRIORITY rubric (LOCKED — India-primary)

| Slug | Definition | UI behavior |
|---|---|---|
| `india-native` | India-only or India-domiciled program (Startup India, MeitY, state missions, IIT incubators) | Top-of-list by default. India flag badge. |
| `accessible-from-india` | Global/US/EU program that explicitly accepts Indian residents or Indian-incorporated companies (YC, MIT 100K, AWS Activate, GCP for Startups, OpenAI Startup Fund where eligible) | Shown by default. "🌐 Open to India" tag. |
| `global-other` | Program with no geo restriction stated (most cloud free tiers, OSS) | Shown by default. No tag. |
| `us-only` | US residents / US-incorporated only | Hidden by default for India-primary view. Surface in "Global / US" sub-tab. |
| `eu-only` | EU-only programs | Hidden by default for India-primary view. Surface in "Global / EU" sub-tab. |
| `other-region` | Region-specific (UK, Singapore, Japan, etc.) | Hidden by default. Surface only when user picks that region. |

When the collector / LLM is uncertain, use `global-other` (most permissive default) AND drop `parse_confidence` to `medium` so the verify queue flags it for human review.

A grant or accelerator can carry BOTH `geo_priority` AND a more granular country list in `eligibility.regions`. The two are not redundant — `geo_priority` drives default sort + UI tabs; `eligibility.regions` is precise truth.

## USE_CASE_TIER rubric (LOCKED — 6-tier scheme, updated 2026-04-26 from Lovable design)

| Tier | Project profile | Resource fit criteria |
|---|---|---|
| `hobby` | Weekend tinkering, learning, throwaway demos | Any free tier qualifies. Even 30-day trials. Sleep-after-inactivity OK. Public-only OK. |
| `personal` | Small personal site / tool. Single user or family. Always-on expected. | Always-free OR refresh-without-CC OR free-tier with no aggressive sleep. Auth + minimal DB. |
| `startup-mvp` | Pre-revenue MVP, ~10-1000 users, want easy upgrade path | Production-grade SLA on free tier, room to grow into paid without rewrite, no surprise overage charges, supports auth + custom domain. |
| `pre-seed` | Bootstrapped / friends-and-family-funded, 1-3 person team, early traction | Free tier sufficient for first 1k–10k MAU. OR: program targets pre-seed founders (e.g. AWS Activate Founders, GCP Start). |
| `seed` | Post-seed-round, ~$500k-$5M raised, 3-15 person team | Free tier as dev/sandbox + meaningful credit programs (AWS Activate Portfolio, GCP for Startups Scale, Azure for Startups Pro). |
| `series-a` | Post-Series-A, paying users + production scale, 15-50 person team | Free tier as dev only; emphasis on enterprise credit programs, accelerator alumni perks, large-scale grants. |

A record can carry MULTIPLE tier slugs. Most quality dev resources fit `["hobby", "personal", "startup-mvp", "pre-seed"]`. Credit programs fit `["pre-seed", "seed", "series-a"]`. Cheap-and-cheerful free tiers fit `["hobby", "personal"]`.

**Negative criteria — when to NOT include a tier:**
- Don't tag `personal` if the provider sleeps containers after 15 min idle on free.
- Don't tag `startup-mvp` if the upgrade path requires a vendor rewrite (e.g. dev-only OSS without a hosted offer).
- Don't tag `startup` if the free tier has request caps that break under any real revenue.
- Don't tag `hobby` for grants — those are application-only, not "spin up tonight."

**Collectors set this heuristically; humans can override.** When the LLM extractor is unsure, write `["hobby"]` (most conservative) and set `parse_confidence: low` so the verify-queue flags it.

## OFFER_TYPE semantics (don't confuse these)

| `offer_type`     | Meaning                                                | Example                         |
|------------------|--------------------------------------------------------|---------------------------------|
| `free-tier`      | Always-free quota, no expiry                           | Cloudflare Workers free plan    |
| `free-credits`   | Currency credits expiring after N days                 | $300 GCP for new accounts       |
| `free-trial`     | Full access, time-limited                              | 14-day Render Pro trial         |
| `free-quota`     | API request / token quota, refills periodically        | Groq daily LLM quota            |
| `grant`          | Non-dilutive cash; application required                | Startup India Seed Fund         |
| `perk`           | Discount or extended free period for partners          | Notion Plus free for startups   |
| `oss`            | Open-source artifact (no quota concept)                | YC startup directory CSV        |

## Validation rules (enforce in the loader, not in `if`-checks scattered around)

- `id`, `provider_id`, `category`, `source_url`, `scraped_at` are required. Reject record if missing.
- `category` MUST be in CATEGORY_ENUM.
- `offer_type` MUST match the enum above.
- `parse_confidence` ∈ {high, medium, low}. Records with `low` are ingested but flagged in the UI with a "verify yourself" badge.
- `scraped_at` ≤ now + 5 min (clock skew tolerance). Reject future timestamps beyond that.
- `currency` and `credit_amount` are both null OR both non-null.
- `eligibility.regions` non-empty array. Use `["global"]` if open to anyone.
- `use_case_tiers` non-empty array, every element ∈ {hobby, personal, startup-mvp, pre-seed, seed, series-a}.
- `tier_fit_rationale` required when `use_case_tiers` includes any of `seed`, `series-a` (forces the collector / LLM to defend the claim).
- `quota_summary`, `duration_summary`, `region_summary` required (drive the three stat tiles in the card UI). All three MUST be ≤ 30 chars to fit the tile layout. Use `Always free`, `Global`, `Rate-limited`, etc.
- `eligibility_summary` required (one short phrase like "Any developer with email", "Any user", "DPIIT-recognized startups").

## Migrations

- Schema version pinned in `schema/VERSION` (single integer).
- Adding an OPTIONAL field → minor bump (e.g. v3 → v4), no migration script needed.
- Adding a REQUIRED field, renaming, or changing enum membership → MUST ship a migration script under `schema/migrations/<NNN>-<slug>.{sql,py}` that backfills history. Never break old records.
- All schema changes go through a `/design` cycle. Never silent.

## What lives OUTSIDE this schema

- Per-category UI metadata (icon, color, tagline) → `web/categories.ts`. Not in the data record.
- User notes / personal ranking → separate `user_notes` table keyed by `provider_id`.
- Scraped raw HTML → `data/raw/`, never embedded in the record.

## Anti-patterns (flag in review)

- Per-category schema variants ("`gpu_offer`" vs "`api_offer`") — collapse to the canonical shape.
- Boolean flags like `is_free`, `is_active` — use `offer_type` and `status` enums.
- Stringly-typed dates ("`expires in 30 days`") — store ISO date.
- Free-text limits ("`a few thousand requests`") — extract a number, drop confidence to `low` if you must guess.
- Records without `scraped_at` — reject at ingest.
- Mutating an existing record on re-scrape — append a new row instead.
