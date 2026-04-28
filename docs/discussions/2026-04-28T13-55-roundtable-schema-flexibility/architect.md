> **Revision of:** initial revision
> **Date / time:** 2026-04-28T13:55 (local IST)
> **Status:** AWAITING USER APPROVAL
> **Source deliberation:** `docs/discussions/2026-04-28T13-55-roundtable-schema-flexibility/`

---

# ResourceOS — Provider Schema Flexibility: Architect Review

## BLOCKERS (confidence 8+)

### B1 — Registry must be machine-readable Pydantic models, not a `dict[str, type]` comment

[PERSONA: System Architect | confidence: 9/10 | source: `agentic-pipeline.md` — `call_llm(..., response_model: type[BaseModel])` contract]

The proposal describes `LIMITS_CANONICAL_KEYS: dict[Category, dict[str, type]]` — a Python runtime dict mapping string keys to Python types. The extractor contract in `agentic-pipeline.md` requires every extraction-style LLM call to pass `response_model: type[BaseModel]` so LiteLLM validates and coerces structured output. A `dict[str, type]` is not a `BaseModel` subclass and cannot be passed as `response_model`. The extractor would fall back to untyped `dict` output, losing all coercion and losing the `parse_confidence: low` escalation that fires when required fields are absent.

**Required action:** Define 12 concrete `BaseModel` subclasses (e.g. `CloudLimits`, `AiApiLimits`, `GrantLimits`) in a new `schema/limits.py`. Export a `LIMITS_MODELS: dict[str, type[BaseModel]]` registry keyed by `Category` slug. All fields `Optional` with `None` defaults — partial extractions are valid and expected. The extractor passes `LIMITS_MODELS[record.category]` as `response_model`. Before DB write: `.model_dump(exclude_none=True)` → the `limits: dict[str, Any]` column. `ProviderRecord.limits` stays `dict[str, Any]` for storage; the typed model is the ingest/extractor contract, not the DB column type.

---

### B2 — No type enforcement on `limits` values: sort and filter will silently fail at query time

[PERSONA: System Architect | confidence: 8/10 | source: `schema/records.py` line ~168 `limits: dict[str, Any] = Field(default_factory=dict)`; PostgreSQL JSONB expression index docs]

Current `limits: dict[str, Any]` passes Pydantic validation for any value, including `{"requests_per_day": "14,400/day"}` (string with comma-separator and unit suffix) — a likely LLM extraction artifact. When the dashboard sorts AI-API records by RPD or filters cloud records by `compute_hours_per_month > 500`, the query will either error on SQLite `CAST` against a non-numeric string, or silently cast to `NULL` in Postgres expression indexes, making records unfilterable without any visible failure. This class of bug is invisible until a user sees all records disappear from a filter.

**Required action:** In each `*Limits` model (from B1), type numeric fields as `int | None` or `float | None`, not `Any`. The `.model_validate(raw_limits)` call at ingest coerces or raises `ValidationError`, surfacing extraction errors at write time rather than at query time. Add a `LimitsValidationError` to the extractor's failure path that increments `parse_confidence` to `low` on coercion failure.

---

### B3 — Multi-sub-service providers (AWS, GCP, Azure) cannot be faithfully represented in a flat `limits` dict

[PERSONA: System Architect | confidence: 8/10 | source: `provider-schema.md` §OFFER_TYPE; AWS Free Tier: EC2 750hr + S3 5GB + Lambda 1M req + RDS 750hr as one "provider"]

AWS Free Tier is one logical record but carries four structurally distinct limit sets (EC2, S3, Lambda, RDS). A flat `limits` dict forces one of three bad options: (a) prefixed keys (`ec2_hours`, `s3_gb`, `lambda_requests`) — pollutes the canonical-key namespace and breaks cross-provider comparison; (b) nested dicts (`{"services": {"ec2": {...}}}`) — GIN containment queries become `limits @> '{"services": {"ec2": {"hours": 750}}}'` which most query builders can't generate and which LLMs populate inconsistently due to nesting depth; (c) one record per sub-service — breaks "show everything free from AWS" as a queryable unit and multiplies records 4x for multi-service providers.

**Required action:** Add `sub_offerings: list[dict] | None = None` to `ProviderRecord` (additive, non-breaking for 41 empty-limits records). Define a `SubOffering` shape in `provider-schema.md`: `{service_name: str, headline: str, limits: dict}`. The parent record's `limits` holds the headline/primary limit (e.g. EC2 hours). Multi-service providers populate `sub_offerings`. Single-offer providers leave it `null`. Map to `sub_offerings JSONB` column in SQLite/Postgres.

---

## RECOMMENDATIONS (confidence 6-7)

### R1 — Hybrid is the correct path; discriminated unions fail the LLM-extractability test

[PERSONA: System Architect | confidence: 7/10 | source: Google SWE Book §Data Model Design; Pydantic discriminated union docs]

Scoring the four alternatives against the five stated user requirements:

| Approach | LLM-extract | DB fit | Future-proof | Migration cost | Verdict |
|---|---|---|---|---|---|
| **Hybrid + typed registry (proposed + B1 fix)** | 9/10 | 8/10 | 9/10 | Low | **Adopt** |
| Discriminated-union Pydantic per category | 5/10 | 6/10 | 4/10 | High | Reject |
| JSON Schema `oneOf` per category | 7/10 | 7/10 | 7/10 | Medium | Fallback only |
| RDF/triple-store | 2/10 | 1/10 | 8/10 | Very high | Reject |

Discriminated unions specifically fail LLM extractability because the extractor must classify the record's category before it can pick the right subclass — a classify-then-extract two-shot pattern that doubles LLM calls and fails for cross-category providers (Supabase = `database` + `auth` + `storage` in a single record). Single-table inheritance in SQLite adds a `type` discriminator column but then every query adds `WHERE category = '...'` predicates that the ORM generates incorrectly for union queries.

**Action:** Adopt hybrid. Implement B1 (typed registry) and B2 (numeric field types). Do not introduce per-category Pydantic subclasses for `ProviderRecord` itself.

---

### R2 — DB strategy: jsonb + GIN for containment; expression indexes for 6 sort-critical keys

[PERSONA: System Architect | confidence: 7/10 | source: Crunchy Data JSONB indexing guide; pganalyze GIN index analysis]

GIN with `jsonb_ops` supports containment (`@>`), key existence (`?`), and `jsonpath` — sufficient for "all AI APIs with `vision_supported`" or "all grants with `sectors_priority` containing `fintech`". GIN does NOT support range scans or ORDER BY. For the dashboard's actual sort queries ("sort cloud by compute hours", "filter AI APIs by RPD > 1000"), a B-tree expression index on the extracted value is required:

```sql
-- SQLite (current) — virtual generated column
ALTER TABLE provider_records
  ADD COLUMN limits_rpd INTEGER
  GENERATED ALWAYS AS (CAST(json_extract(limits, '$.rpd') AS INTEGER)) VIRTUAL;
CREATE INDEX idx_provider_limits_rpd ON provider_records(limits_rpd)
  WHERE category = 'ai-api';

-- Postgres (future) — expression index
CREATE INDEX idx_limits_rpd ON provider_records
  (((limits->>'rpd')::int))
  WHERE category = 'ai-api';
```

Apply expression indexes for exactly 6 keys: `compute_hours_per_month` (cloud), `rpd` (ai-api), `grant_amount` (grant), `storage_gb` (cloud + database + storage), `context_window` (ai-api), `investment_amount` (accelerator). All other limits stay in the blob. SQLite's `json_extract` + `CAST` is the SQLite equivalent — add to `schema/migrations/002-limits-expression-indexes.sql`.

**Action:** Create `schema/migrations/002-limits-expression-indexes.sql` with both SQLite and Postgres variants, comment-delimited. Include the `always_on` boolean virtual column for cloud (load-bearing for the `personal` tier filter in the dashboard sidebar).

---

### R3 — Canonical key set per category (12 categories, evidence-grounded)

[PERSONA: System Architect | confidence: 6/10 | source: `data/seed.json` 10 enriched records; `provider-schema.md` category enum]

Evidence from the 10 hand-enriched seed records (Vercel, Render, Cloudflare Workers, Groq, Gemini, Supabase, R2, AWS Activate, YC, Startup India Seed) + 4 cloud records (AWS, GCP, Azure, Oracle) provides natural alignment on canonical keys:

**`cloud`**: `compute_hours_per_month`, `vcpu`, `ram_gb`, `storage_gb`, `bandwidth_gb`, `cold_start_seconds`, `regions`, `always_on`, `custom_domain_supported`

**`gpu`**: `gpu_model`, `vram_gb`, `hours_per_week`, `preemptible`, `max_session_hours`, `regions`

**`ai-api`**: `models`, `rpm`, `rpd`, `tpm`, `tpd`, `context_window`, `vision_supported`, `function_calling`, `embedding_supported`, `free_quota_resets`

**`database`**: `storage_gb`, `row_limit`, `connections`, `branching_supported`, `regions`, `backup_days`, `read_replicas`

**`storage`**: `storage_gb`, `egress_gb`, `operations_class_a`, `operations_class_b`, `regions`

**`auth`**: `monthly_active_users`, `social_providers`, `mfa_supported`, `custom_domain_supported`

**`observability`**: `log_retention_days`, `metrics_retention_days`, `traces_supported`, `seats`

**`grant`**: `grant_amount`, `currency`, `equity_taken_percent`, `decision_timeline_months`, `sectors_priority`, `application_url`, `cohort_size`

**`accelerator`**: `investment_amount`, `equity_taken_percent`, `batch_duration_weeks`, `acceptance_rate_percent`, `remote_supported`, `alumni_count`

**`startup-credit`**: `credit_amount_usd`, `validity_months`, `eligible_stages`, `requires_investor_backing`

**`perk`**: `discount_percent`, `free_months`, `eligible_user_types`, `stacking_allowed`

**`oss`**: `stars`, `license`, `language`, `last_commit_date`, `demo_url`

Note on `cloud`: `always_on` is a first-class boolean that drives the `personal` tier eligibility filter in the dashboard sidebar. It must be a virtual/generated column (per R2), not buried in the blob.

Note on `ai-api`: `models` should be `list[str]` — both Groq and Gemini seed records show arrays of model IDs. In the `AiApiLimits` Pydantic model, type this as `list[str] | None`.

---

### R4 — LLM-readable bar: OpenAPI/JSON Schema, not JSON-LD; schema in extractor system prompt

[PERSONA: System Architect | confidence: 6/10 | source: `agentic-pipeline.md` extractor prompt spec; `freellm-router.md` `response_model` contract]

JSON-LD is over-engineering for this scale and posture (personal-first, 55–500 records). The right bar for LLM-readability is: export `ProviderRecord.model_json_schema()` and each `*Limits.model_json_schema()` to `schema/provider-record.schema.json`. Include the relevant category's limits JSON schema in the extractor's system prompt (stored in `agents/prompts/extractor.md` per the pipeline rule). LiteLLM's `response_format` with `json_schema` mode constrains extractor output at the API level — this is what actually enforces structure, not a linked-data URI.

For downstream consumers (other agents, external scrapers), the FastAPI `/api/providers` response should include `"$schema": "https://raw.githubusercontent.com/.../schema/provider-record.schema.json"` in the response envelope's `meta` block. No additional tooling required.

**Action:** Add a `schema/export_schema.py` script that writes `ProviderRecord.model_json_schema()` + each `*Limits.model_json_schema()` to `schema/provider-record.schema.json` as a `$defs`-based composite. Run as part of CI (`pyright + ruff + export_schema.py`) to keep schema in sync with code.

---

## OBSERVATIONS (confidence 4-5)

### O1 — Two-model surface between `schema/records.py` and `backend/main.py` will recur

[PERSONA: System Architect | confidence: 5/10 | source: timeline observations 4773 / 4782]

The OfferType "free-tier" divergence (now fixed per observation 4782) between `schema/records.py` and the API response model in `backend/main.py` is a structural maintenance risk, not a one-time bug. Any field added to `ProviderRecord` that isn't mirrored in the API model silently drops from the response. The canonical fix is a `ProviderPublicResponse` that is a projection of `ProviderRecord` via `model.model_dump(include={...})` — no second class definition. Medium urgency before v0.2 ships new fields from the agentic extractor.

### O2 — `sys.path` manipulation + `noqa: E402` in `backend/main.py` is a package layout smell

[PERSONA: System Architect | confidence: 4/10 | source: timeline observation 3828; Google Python Style Guide §Imports]

`sys.path` hacking to import `schema/` from `backend/main.py` indicates `schema/` is not a proper installable package. Per Google Python Style Guide, relative imports between packages require a proper `pyproject.toml` workspace setup. This will cause import ordering and editable-install failures when `agents/` and `pipeline/` also import from `schema/`. Low severity for v0.1 solo; medium urgency before v0.2.

### O3 — `always_on` is currently in `limits` blob but drives tier filter; should be a top-level field

[PERSONA: System Architect | confidence: 4/10 | source: `provider-schema.md` §USE_CASE_TIER rubric — "Don't tag `personal` if provider sleeps containers after 15 min idle on free"]

The personal tier rubric explicitly depends on whether a provider is always-on. This is a filter-critical boolean that the dashboard sidebar radio button depends on. Querying `json_extract(limits, '$.always_on')` on every filter operation is wasteful. Consider promoting `always_on: bool | None = None` to a top-level `ProviderRecord` field alongside `india_accessible`. Additive, non-breaking for existing records.

---

## ASSIGNED ACTION

Implement `schema/limits.py` with 12 typed `BaseModel` subclasses (all fields `Optional`), a `LIMITS_MODELS: dict[str, type[BaseModel]]` registry, and a `validate_limits(category: str, raw: dict) -> dict` utility that calls `.model_validate(raw).model_dump(exclude_none=True)`. Wire this into `ProviderRecord` as a `@field_validator('limits', mode='before')` on `schema/records.py`. This single file resolves B1 and B2, provides the extractor's `response_model`, and keeps the DB column as `dict[str, Any]` (jsonb) with no schema migration required.

---

## APPENDIX (confidence 1-3 speculative)

### A1 — SQLite `json_each` virtual projections for ad-hoc analytics before Postgres migration

[PERSONA: System Architect | confidence: 2/10]

SQLite's `json_each(limits)` produces a virtual table of `(key, value)` rows per record — usable for ad-hoc analytics without any schema change. Not worth building now; worth knowing for exploratory queries before the Postgres migration adds expression indexes.

### A2 — Pydantic `Field(title=..., description=...)` on `*Limits` models can auto-generate frontend label maps

[PERSONA: System Architect | confidence: 2/10]

If each `*Limits` field carries `Field(title="Requests/Day", description="...")` metadata, a build step can emit `frontend/lib/limits-labels.ts` from `model_json_schema()`, eliminating hand-maintenance of the `LimitsView` label map in TypeScript.

### A3 — RDF is the correct eventual model only if ResourceOS pivots to a public knowledge graph

[PERSONA: System Architect | confidence: 1/10]

If the project pivots from personal dashboard to "structured global knowledge graph of developer resources" (the FreeStackHub public-product angle in `project-idea.md`), the long-term correct data model is RDF with SPARQL. The JSONB hybrid is a practical stepping stone that doesn't foreclose this path.

---

Sources:
- [Indexing JSONB in Postgres — Crunchy Data](https://www.crunchydata.com/blog/indexing-jsonb-in-postgres)
- [Understanding Postgres GIN Indexes — pganalyze](https://pganalyze.com/blog/gin-index)
- [PostgreSQL JSONB documentation](https://www.postgresql.org/docs/current/datatype-json.html)
