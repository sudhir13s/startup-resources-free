# Project Rule: Provider Record Schema (v2)

> The canonical shape of a "provider offering" record. Every refresh extraction emits this
> shape. Every UI/API consumes this shape. Schema changes are migrations, not silent edits.
> **Source of truth: `domain/records.py`** (the `ProviderRecord`, `Service`, `Credit`, `Link`,
> `Eligibility` Pydantic models) and `domain/taxonomy.py` (every enum). This file explains the
> shape in prose; when they disagree, the code wins — update this file to match.

## Why a fixed schema

Tempting to give each category its own schema. Don't. A single normalized shape makes:

- Cross-category ranking ("best free stack for AI app") trivial.
- The dashboard one component instead of seven.
- History diffs comparable across providers.

## v2 change: an offer, broken into services

A record is one vendor **offer** (AWS Free Tier, AWS Activate, Groq free quota) — not one
service. A multi-service offer lists each service in `services[]` with its own `category`, so
"AWS Free Tier" matches the Database, Storage, and AI filters simultaneously through the
computed `categories` field, instead of needing one record per AWS service.

## The shape (canonical — mirrors `domain/records.py::ProviderRecord`)

```jsonc
{
  // --- Identity ---
  "provider_id": "aws-free-tier",       // slug, pattern ^[a-z0-9]+(-[a-z0-9]+)*$, stable
  "name": "AWS Free Tier",              // display name
  "vendor": "AWS",                      // groups offers from the same company
  "category": "cloud",                  // primary Category enum (see below)
  "source_urls": ["https://aws.amazon.com/free/"],  // pages refresh reads; min 1, http(s) only

  // --- The offer ---
  "offer_type": "free-tier",            // free-tier | free-credits | free-trial | free-quota | grant | perk | oss
  "headline": "12 months free, plus always-free services",
  "highlights": ["EC2 t2.micro 750 hrs/mo", "S3 5 GB", "..."],  // TL;DR bullets, max 6
  "services": [
    {
      "name": "EC2",
      "category": "cloud",              // a ResourceCategory — can differ per service
      "service_type": "vm",             // free text: vm, serverless, sql, nosql, object-storage, llm, ...
      "pricing_layer": "12-month",      // always-free | 12-month | trial | credit | quota
      "summary": "750 hrs/mo t2.micro or t3.micro",
      "limits": [
        {"label": "Instance hours", "value": 750, "unit": "hours", "period": "month"}
      ],
      "notes": null
    }
  ],
  "credits": [
    {"label": "AWS Activate credit", "amount": 1000, "currency": "USD", "duration_days": 730, "conditions": "..."}
  ],

  // --- Card stat tiles (each <= 40 chars) ---
  "quota_summary": "750 hrs/mo · 5 GB S3",
  "duration_summary": "12 months",
  "region_summary": "Global",
  "eligibility_summary": "Any AWS account",

  // --- Eligibility, access, caveats ---
  "eligibility": {"regions": ["global"], "user_types": ["any"], "company_age_max_years": null, "funding_max_usd": null},
  "access_method": "signup",            // api-key | oauth | signup | email-verify | github-auth | manual-apply | invite-only | contact-sales | unknown
  "claim_steps": ["Create an AWS account", "Activate the Free Tier in Billing"],
  "restrictions": ["Free Tier resets per AWS account, not per card"],
  "gotchas": ["Overage bills at standard rates with no hard cap"],
  "after_free_period": "Standard on-demand pricing applies",
  "links": [{"label": "Free Tier FAQ", "url": "https://aws.amazon.com/free/free-tier-faqs/"}],

  // --- Fit ---
  "geo_priority": "global-other",       // see GEO_PRIORITY rubric below
  "always_on": true,
  "use_case_tiers": ["hobby", "personal", "startup-mvp"],  // see USE_CASE_TIER rubric below
  "tier_fit_rationale": "...",          // required when tiers include seed or series-a

  // --- Quality / freshness ---
  "parse_confidence": "high",           // high | medium | low
  "source_method": "manual",            // manual | llm | api
  "last_verified_at": "2026-09-25",
  "scraped_at": "2026-09-25T11:47:00Z", // UTC ISO 8601
  "expiry_date": null,
  "status": "active",                   // active | reduced | ended | unknown
  "notes": null

  // --- Derived, never stored as input (computed_field on ProviderRecord) ---
  // "categories": ["cloud", "database", "storage"]  — primary category + every service category
  // "card_variant": "resource"          — "resource" or "funds", from card_variant(category)
  // "india_accessible": true            — geo_priority in {india-native, accessible-from-india, global-other}
}
```

`ProviderRecord.to_storage()` strips the derived fields before persisting; `from_storage()` /
the `_drop_derived` validator accept and discard them on read, so a record round-tripped through
the API (e.g. nested in a `VerifyItem`) re-validates without special-casing.

## CATEGORY_ENUM (from `domain/taxonomy.py` — don't invent variants)

`Category` = `ResourceCategory | FundCategory`. `ResourceCategory` renders on `/resources`;
`FundCategory` renders on `/funds` (`card_variant()` decides which, keyed off the primary
`category`). A `Service.category` uses the same `ResourceCategory` values.

```
# ResourceCategory (/resources)
cloud           — compute, hosting, PaaS, serverless, networking (AWS, GCP, Vercel, Fly)
gpu             — GPU compute (Colab, RunPod, Lambda)
ai-api          — hosted model inference (Groq, OpenRouter, HF Inference)
database        — managed DB (Supabase, Neon, Mongo Atlas)
storage         — object / blob storage (R2, B2)
auth            — managed auth (Clerk, Auth0, Supabase Auth)
observability   — logs / metrics / errors (Grafana Cloud, Sentry, Logflare)
domain          — domains / DNS / email
dev-tools       — CI/CD, repos, codespaces
oss             — useful open-source repo (template, framework, tool)
learning        — free course / cert / paper feed

# FundCategory (/funds)
startup-credit  — bundled credits (AWS Activate, GCP for Startups, Azure for Startups)
grant           — non-dilutive funding (govt, foundation, sector-specific)
accelerator     — accelerator / incubator programs
perk            — SaaS discount (Notion, HubSpot, Stripe Atlas)
```

`domain/taxonomy.py::normalize_category` maps legacy/plural aliases (`hosting`→`cloud`,
`databases`→`database`, `grants`→`grant`, etc.) to the canonical slug so old seed rows and LLM
output don't hard-fail. If you need a new slug, add it to `taxonomy.py` AND migrate existing
records — don't sprinkle ad-hoc slugs anywhere else.

## GEO_PRIORITY rubric (LOCKED — India-primary)

| Slug | Definition | UI behavior |
|---|---|---|
| `india-native` | India-only or India-domiciled program (Startup India, MeitY, state missions, IIT incubators) | Top-of-list by default. India flag badge. |
| `accessible-from-india` | Global/US/EU program that explicitly accepts Indian residents or Indian-incorporated companies (YC, MIT 100K, AWS Activate, GCP for Startups, OpenAI Startup Fund where eligible) | Shown by default. "🌐 Open to India" tag. |
| `global-other` | Program with no geo restriction stated (most cloud free tiers, OSS) | Shown by default. No tag. |
| `us-only` | US residents / US-incorporated only | Hidden by default for India-primary view. Surface in "Global / US" sub-tab. |
| `eu-only` | EU-only programs | Hidden by default for India-primary view. Surface in "Global / EU" sub-tab. |
| `other-region` | Region-specific (UK, Singapore, Japan, etc.) | Hidden by default. Surface only when user picks that region. |

When `refresh/extract.py` is uncertain, use `global-other` (most permissive default) AND drop `parse_confidence` to `medium` so the record surfaces for review.

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

**`refresh/extract.py` sets this heuristically; humans can override** via a `data/providers_seed.json` correction (re-applied on next boot — see `agentic-pipeline.md`). When the extractor is unsure, write `["hobby"]` (most conservative) and set `parse_confidence: low` so the record surfaces for review.

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

## Validation rules (enforced by `ProviderRecord`'s Pydantic validators — `domain/records.py`)

- `provider_id`, `name`, `vendor`, `category`, `source_urls`, `offer_type`, `headline`,
  `use_case_tiers` are required (`model_config = ConfigDict(extra="forbid")` — unknown fields
  are rejected, not silently dropped).
- `provider_id` MUST match `^[a-z0-9]+(-[a-z0-9]+)*$`.
- `category` and `offer_type` are coerced through `normalize_category` / `normalize_offer_type`
  before validation, so legacy aliases don't hard-fail.
- `access_method` unrecognized by the LLM is coerced to `"unknown"` rather than failing the
  whole record (`_unknown_access_method` validator) — extraction failures degrade one field,
  not the record.
- `source_urls` and every `Link.url` MUST start with `http://` or `https://`.
- `quota_summary`, `duration_summary`, `region_summary`, `eligibility_summary` MUST be
  ≤ `TILE_MAX_CHARS` (40) to fit the card stat tiles.
- `highlights` holds at most 6 bullets.
- `use_case_tiers` non-empty, every element ∈ {hobby, personal, startup-mvp, pre-seed, seed, series-a}.
- `Credit.currency`, when set, MUST be a 3-letter ISO 4217 code (uppercased automatically).
- `parse_confidence` ∈ {high, medium, low}. Records with `low` surface on the Candidates/Changes
  pages for human review rather than being rejected.

## Migrations

- `storage/migrations.py` owns SQLite schema migrations (numbered, applied on every API boot
  before any query runs).
- Adding an OPTIONAL field to `ProviderRecord` needs no migration — SQLite stores the record as
  JSON; only structural (table/column) changes need a `storage/migrations.py` entry.
- Adding a REQUIRED field, renaming, or changing enum membership is still a breaking change to
  every stored version — write a migration that backfills history, and go through a `/design`
  cycle. Never silent.

## What lives OUTSIDE this schema

- Per-category UI metadata (icon, color, tagline) → `frontend/lib/` (mirrors `domain/taxonomy.py`,
  kept equal by a test). Not in the data record.
- Field-level version history and diffs → `domain/changes.py` + the `changes` table in
  `storage/`, not embedded in the current record.
- Raw fetched page text → not persisted beyond the hash used by the refresh hash-gate.

## Anti-patterns (flag in review)

- Per-category schema variants ("`gpu_offer`" vs "`api_offer`") — collapse to the canonical shape.
- Boolean flags like `is_free`, `is_active` — use `offer_type` and `status` enums.
- Stringly-typed dates ("`expires in 30 days`") — store ISO date.
- Free-text limits ("`a few thousand requests`") — extract a number into `Limit.value`, drop
  confidence to `low` if you must guess.
- Records without `scraped_at` — the field has a default (`_utcnow()`), but every stored record
  should carry a real fetch timestamp, not the default.
- Mutating an existing record's history on re-scrape — `storage/` always appends a new version.
