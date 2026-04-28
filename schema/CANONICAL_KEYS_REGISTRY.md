# Canonical Keys Registry — `limits` field per category

> **Source of truth** for every canonical key the agentic extractor
> targets when populating `ProviderRecord.limits`. PR-review gate
> required for every change here.
>
> Resolves CTO B2 (8/10) from the [2026-04-28 schema-flexibility
> roundtable](../docs/discussions/2026-04-28T13-55-roundtable-schema-flexibility/).
>
> This file is human-readable convention. The machine-readable
> registry is [`schema/limits.py`](./limits.py) — every key here
> MUST appear as a typed field on the corresponding `*Limits` class.

---

## Why this file exists

The `ProviderRecord.limits` field is `dict[str, Any]` for storage
flexibility. Without a frozen registry of expected keys per category,
three things go wrong:

1. **Extractor drift** — the LLM extractor for one provider page emits
   `compute_hours_per_month`; for the next provider it emits `cpu_hours`
   or `vcpu_hours_monthly`. Same data, three keys. Sort/filter breaks.
2. **Frontend label-map rot** — `LimitsView` maintains pretty-print
   labels per key. Without a frozen list, every drift requires a label
   update.
3. **DB index brittleness** — Postgres expression indexes
   (`CREATE INDEX ... ON ((limits->>'compute_hours_per_month')::int)`)
   are keyed by name. Drift breaks the index silently.

The registry is **convention, not validation**. `_LimitsBase` uses
`extra="allow"` so non-canonical keys still pass through (forward
compat). The registry tells the extractor what to LOOK FOR. Anything
extra is a candidate for promotion to canonical via a PR.

---

## Governance

- **Adding a key:** PR that touches both this file AND
  `schema/limits.py`. The corresponding `*Limits` class gains a typed
  field. Reviewer checks that the type is the most-restrictive that
  still fits real data (`int | None` over `float | None` over `str | None`).
- **Renaming a key:** breaking change. Requires schema/VERSION bump
  AND a migration script under `schema/migrations/<NNN>-<slug>.{sql,py}`
  that backfills history.
- **Removing a key:** breaking change. Same as rename — write a
  migration that nulls the column on existing records, version-bump.
- **No silent edits.** This file is reviewed; the LLM extractor's
  prompt is updated to inject only the relevant category's keys per
  call (per CTO R2 — keeps prompt size bounded).

---

## Resource-side categories

### `cloud` — IaaS / PaaS free tiers

| Key | Type | Notes |
|---|---|---|
| `compute_hours_per_month` | `int` | vCPU-hours included free per month, or always-free instance hours like EC2 t2.micro 750h. |
| `vcpu` | `float` | vCPU count of the included instance class. |
| `ram_gb` | `float` | RAM in GiB on the included instance class. |
| `storage_gb` | `float` | Free block / disk storage in GiB. |
| `bandwidth_gb` | `float` | Free egress bandwidth in GiB per month. |
| `cold_start_seconds` | `float` | Approximate cold-start latency. Render free spin-down, Lambda first invoke. |
| `regions` | `list[str]` | Regions included in the free tier. |
| `always_on` | `bool` | True = no idle spin-down. Drives the `personal` tier eligibility filter. |
| `custom_domain_supported` | `bool` | |
| `ssl_certificates` | `str` | e.g. `"Auto Let's Encrypt"`. |
| `commercial_use_allowed` | `bool` | False on Vercel Hobby — flagged so users don't hit ToS surprises post-launch. |
| `max_request_size_mb` | `float` | |
| `max_response_size_mb` | `float` | |

**Sort/filter targets:** `compute_hours_per_month` (B-tree expression index), `always_on` (B-tree expression index — drives `personal` tier filter).

---

### `hosting` — frontend / static-site hosting (Vercel, Netlify, Cloudflare Pages)

Inherits all `cloud` keys. Adds:

| Key | Type | Notes |
|---|---|---|
| `build_minutes_per_month` | `int` | |
| `serverless_invocations_per_day` | `int` | |
| `serverless_function_max_duration_s` | `int` | |
| `serverless_function_max_memory_mb` | `int` | |
| `edge_function_invocations_per_day` | `int` | |
| `preview_deployments` | `str` | `"Unlimited"` typical. |
| `image_optimizations_per_month` | `int` | |

---

### `gpu` — Colab / Kaggle / RunPod / Lambda Labs / Paperspace

| Key | Type | Notes |
|---|---|---|
| `gpu_model` | `str` | |
| `vram_gb` | `float` | |
| `hours_per_week` | `float` | |
| `max_session_hours` | `float` | |
| `concurrent_sessions` | `int` | |
| `preemptible` | `bool` | |
| `runtime_supported` | `list[str]` | |
| `idle_timeout_minutes` | `int` | |
| `regions` | `list[str]` | |

---

### `ai-api` — LLM / vision / embedding / TTS / STT inference APIs

| Key | Type | Notes |
|---|---|---|
| `models` | `list[str]` | Model IDs available on the free tier. |
| `rpm` | `int` | Requests per minute. |
| `rpd` | `int` | Requests per day. |
| `tpm` | `int` | Tokens per minute. |
| `tpd` | `int` | Tokens per day. |
| `context_window` | `int` | Max input + output tokens per request. |
| `vision_supported` | `bool` | |
| `function_calling_supported` | `bool` | |
| `structured_output_supported` | `bool` | |
| `audio_input_supported` | `bool` | |
| `audio_output_supported` | `bool` | |
| `embedding_supported` | `bool` | |
| `image_generation_supported` | `bool` | |
| `video_generation_supported` | `bool` | |
| `openai_compatible_api` | `bool` | |
| `free_quota_resets` | `str` | `"daily"`, `"monthly"`, `"rolling-30-days"`. |
| `regions` | `list[str]` | |
| `data_used_for_training` | `str` | Privacy flag for Gemini free tier, etc. |

**Sort/filter targets:** `rpd`, `context_window`.

---

### `database` (alias `databases`) — Supabase, Neon, PlanetScale, Mongo Atlas, Upstash, Pinecone

| Key | Type | Notes |
|---|---|---|
| `database_size_mb` | `int` | |
| `database_engine` | `str` | `"PostgreSQL 15"`, `"MySQL 8"`, etc. |
| `row_limit` | `int` | |
| `connections` | `int` | |
| `branching_supported` | `bool` | Neon-style. |
| `point_in_time_recovery` | `str` | `"Paid only"` or duration. |
| `auto_pause_after_days_idle` | `int` | |
| `daily_backups_retention_days` | `int` | |
| `realtime_supported` | `bool` | |
| `vector_supported` | `bool` | pgvector / native vector index. |
| `read_replicas` | `int` | |
| `regions` | `list[str]` | |

**Sort/filter targets:** `storage_gb` (shared with cloud + storage; one expression index covers all three).

---

### `storage` — R2, B2, S3-compatible free tiers

| Key | Type | Notes |
|---|---|---|
| `storage_gb` | `float` | |
| `egress_gb_per_month` | `float` | |
| `egress_fee` | `str` | `"$0"` for R2 (the killer feature); `"$0.09/GB"` for AWS. |
| `operations_class_a` | `int` | |
| `operations_class_b` | `int` | |
| `api_compatibility` | `str` | e.g. `"S3-compatible"`. |
| `versioning` | `bool` | |
| `lifecycle_rules` | `bool` | |
| `presigned_urls` | `bool` | |
| `max_object_size_gb` | `float` | |
| `regions` | `list[str]` | |

---

### `auth` — Clerk, Auth0, Supabase Auth, Stytch

| Key | Type | Notes |
|---|---|---|
| `monthly_active_users` | `int` | |
| `social_providers` | `list[str]` | OAuth providers supported. |
| `mfa_supported` | `bool` | |
| `sso_supported` | `bool` | |
| `custom_domain_supported` | `bool` | |
| `webhooks_supported` | `bool` | |
| `organizations_supported` | `bool` | |
| `seats` | `int` | |

---

### `observability` — Sentry, Grafana Cloud, Logflare, Axiom

| Key | Type | Notes |
|---|---|---|
| `events_per_month` | `int` | |
| `log_retention_days` | `int` | |
| `metrics_retention_days` | `int` | |
| `traces_supported` | `bool` | |
| `seats` | `int` | |
| `dashboards_count` | `int` | |

---

### `domain` (alias `domains`) — Cloudflare DNS, Namecheap

| Key | Type | Notes |
|---|---|---|
| `free_tlds` | `list[str]` | |
| `dns_records_max` | `int` | |
| `email_forwarding_supported` | `bool` | |

---

### `learning` — Coursera audit, Kaggle Learn, free certs

| Key | Type | Notes |
|---|---|---|
| `course_count` | `int` | |
| `certificate_supported` | `bool` | |
| `cost_for_certificate_usd` | `float` | |
| `duration_hours` | `float` | |

---

## Fund-side categories

### `grant` (alias `grants`) — Startup India, MeitY, NIH SBIR, Mozilla MOSS

| Key | Type | Notes |
|---|---|---|
| `grant_amount` | `float` | In `currency` (top-level field on ProviderRecord). |
| `currency` | `str` | ISO 4217 — also lives on the parent record. |
| `application_window` | `str` | `"Rolling"` or `"Quarterly"` or specific dates. |
| `decision_timeline_months` | `str` | `"3-6"` typical for grants. |
| `sectors_priority` | `list[str]` | `["AI/ML", "Deep tech", "Climate"]`, etc. |
| `incubator_partner_required` | `bool` | True for Startup India Seed Fund. |
| `milestones_required` | `bool` | |
| `tranches_typical` | `str` | `"3 (40% / 30% / 30%)"`. |
| `reporting_required` | `str` | `"Quarterly utilization certificate"`. |
| `company_age_max_years` | `int` | Founder-friendly cutoff. |
| `indian_subsidiary_required` | `bool` | India-program flag. |

**Sort/filter targets:** `grant_amount` (B-tree expression index).

---

### `accelerator` (alias `accelerators`) — YC, Techstars, NASSCOM 10000, Antler

| Key | Type | Notes |
|---|---|---|
| `investment_amount` | `float` | |
| `investment_structure` | `str` | `"$125k SAFE + $375k uncapped post-money SAFE with MFN"`. |
| `equity_taken_percent` | `float` | |
| `batches_per_year` | `int` | |
| `batch_duration_weeks` | `int` | |
| `acceptance_rate_percent` | `float` | |
| `alumni_network_size` | `int` | |
| `alumni_perks_value_usd` | `float` | |
| `office_space` | `str` | |
| `remote_supported` | `bool` | |
| `demo_day_investors_attending` | `int` | |

**Sort/filter targets:** `investment_amount` (B-tree expression index).

---

### `startup-credit` (alias `startup-credits`) — AWS Activate, GCP for Startups, Azure for Startups

| Key | Type | Notes |
|---|---|---|
| `credit_amount_usd` | `float` | |
| `duration_months` | `int` | |
| `eligible_stages` | `list[str]` | `["pre-seed", "seed", "series-a"]`. |
| `eligible_age_max_years` | `int` | |
| `requires_investor_backing` | `bool` | |
| `services_eligible` | `list[str]` | What the credits can be used for. |
| `support_included` | `str` | `"Business support ($100/mo value)"`. |
| `training_credits_usd` | `float` | |
| `regions` | `list[str]` | |
| `tiers` | `dict` | Per-tier breakdown for multi-tier programs (AWS Activate Founders / Portfolio / Enterprise). |

---

### `perk` (alias `perks`) — Notion / Stripe / HubSpot for Startups

| Key | Type | Notes |
|---|---|---|
| `perk_value_usd` | `float` | |
| `discount_percent` | `float` | |
| `free_months` | `int` | |
| `eligible_user_types` | `list[str]` | |
| `partner_required` | `str` | `"YC alumni"`, `"$.edu email"`, etc. |
| `activation_method` | `str` | |
| `expiry_months` | `int` | |
| `stacking_allowed` | `bool` | |

---

### `oss` — Open-source artifacts (boilerplates, frameworks, model weights)

| Key | Type | Notes |
|---|---|---|
| `stars` | `int` | GitHub star count. |
| `license` | `str` | `"MIT"`, `"Apache-2.0"`, `"AGPL-3.0"`, etc. |
| `language` | `str` | Primary language. |
| `last_commit_date` | `str` | ISO date. |
| `demo_url` | `str` | |
| `self_hosted_only` | `bool` | |

---

## Sort/filter target index (Phase 4 expression indexes)

Per Architect R2, exactly 6 keys get B-tree expression indexes:

| Key | Categories using it | DB index |
|---|---|---|
| `compute_hours_per_month` | `cloud`, `hosting` | `idx_limits_compute_hours` (partial: `WHERE category IN ('cloud','hosting')`) |
| `rpd` | `ai-api` | `idx_limits_rpd` (partial: `WHERE category = 'ai-api'`) |
| `grant_amount` | `grant` | `idx_limits_grant_amount` |
| `storage_gb` | `cloud`, `database`, `storage` | `idx_limits_storage_gb` |
| `context_window` | `ai-api` | `idx_limits_context_window` |
| `investment_amount` | `accelerator` | `idx_limits_investment_amount` |

Plus one virtual generated column on `cloud` records: `always_on` (drives `personal` tier filter).

All other limit keys stay in the JSONB blob and use GIN containment index for "any record with this key set" queries.
