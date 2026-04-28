# Roundtable — Provider Schema Flexibility

> **Date / time:** 2026-04-28T13:55 (IST)
> **Participants:** System Architect (`architect.md`) + CTO (`cto.md`)
> **Status:** AWAITING USER APPROVAL on consolidated action plan
> **Question:** Hybrid (canonical-keys-per-category in flexible `limits`) vs pure-rigid (per-category Pydantic subclasses) vs pure-flexible (loose dict)?

---

## Verdict

**GO on hybrid** — both specialists converge with confidence 7–8/10 against alternatives. Discriminated-union Pydantic per category is REJECTED (architect R1, fails LLM-extractability test for cross-category providers like Supabase = database + auth + storage). RDF / triple-store REJECTED. JSON Schema `oneOf` is a fallback only, not the primary path.

---

## Convergence (raised by both → confidence escalated)

| Theme | Architect | CTO | Combined |
|---|---|---|---|
| Hybrid is correct path | R1 (7) | GO (8) | **8 — adopt** |
| Round-trip / schema-divergence test in CI | O1 (5) | B1 (9) + ASSIGNED | **9 — must-do first** |
| Need typed registry / canonical-key freeze | B1 (9) + R3 (6) | B2 (8) | **9 — must-do** |
| Window to refactor is now (41 empty `limits`) | implicit | O2 (5) | **6 — act before v0.2** |

---

## Solo findings (specialist-only — preserve, do not suppress)

| Finding | Source | Confidence | Why it matters |
|---|---|---|---|
| Limit values must be typed numerics not `Any` (sort/filter silently fails) | Architect B2 | 8 | Bug invisible until users see filters return zero records |
| Multi-service providers need `sub_offerings: list[dict]` field on ProviderRecord | Architect B3 | 8 | AWS/GCP/Azure cannot be represented faithfully in flat `limits` |
| jsonb + GIN for containment + 6 B-tree expression indexes for sort-critical keys | Architect R2 | 7 | DB strategy concrete enough to migrate to Postgres later |
| Export `model_json_schema()` to `schema/provider-record.schema.json` for LLM consumers | Architect R4 | 6 | LLM-readable bar; OpenAPI not JSON-LD |
| Promote `always_on: bool` to top-level ProviderRecord field | Architect O3 | 4 | Personal-tier filter depends on this; querying `json_extract` per row is wasteful |
| `sys.path` hacking + `noqa: E402` is a package-layout smell | Architect O2 | 4 | Will bite when `agents/` and `pipeline/` also import from `schema/` |
| Pydantic v2 `dict[str,Any]` is low-risk on this stack — no parallel TypedDicts | CTO R1 | 7 | Confirms hybrid feasibility |
| Extractor prompt token cost bounded — category-scoped injection (only that category's keys per call) | CTO R2 | 6 | Prevents prompt explosion |

---

## Consolidated action plan (in execution order)

### Phase 0 — pre-condition (MUST land first)

1. **`tests/test_schema_roundtrip.py`** — round-trip test that validates a sample seed record through `ProviderRecord.model_validate()` AND `backend/main.py` API response. Catches `OfferType` and any future enum/field divergence between `schema/records.py` and `backend/main.py` permanently. (CTO B1 + ASSIGNED, Architect O1.)
2. **Confirm `mypy --strict`** is wired in CI against `schema/` and `backend/`. (CTO R1 ACTION.)

### Phase 1 — typed limits registry

3. **Create `schema/limits.py`** — 12 typed `BaseModel` subclasses (`CloudLimits`, `GpuLimits`, `AiApiLimits`, `DatabaseLimits`, `StorageLimits`, `AuthLimits`, `ObservabilityLimits`, `GrantLimits`, `AcceleratorLimits`, `StartupCreditLimits`, `PerkLimits`, `OssLimits`). All fields `Optional`. Numeric fields typed `int | None` / `float | None` (Architect B2). (Architect B1 + ASSIGNED.)
4. **Export `LIMITS_MODELS: dict[str, type[BaseModel]]`** keyed by `Category` slug.
5. **Add `validate_limits(category: str, raw: dict) -> dict`** utility that calls `.model_validate(raw).model_dump(exclude_none=True)`.
6. **Wire as `@field_validator('limits', mode='before')`** on `schema/records.py::ProviderRecord` — DB column stays `dict[str, Any]`, but writes go through coercion. (Architect ASSIGNED.)

### Phase 2 — multi-service support

7. **Add `sub_offerings: list[dict] | None = None`** to `ProviderRecord` and define `SubOffering` shape in `provider-schema.md`. AWS / GCP / Azure migration: move per-service breakdowns out of `limits['always_free_layer']` etc. into `sub_offerings`. (Architect B3.)
8. **Promote `always_on: bool | None`** to top-level `ProviderRecord` field. Migrate the 4 cloud records' `limits.always_on` (where present) to the top-level field. (Architect O3.)

### Phase 3 — registry + governance

9. **`schema/CANONICAL_KEYS_REGISTRY.md`** — per-category one-line description per key. PR review gate enforced. (CTO B2 ACTION.)
10. **Update `agents/prompts/extractor.md`** to inject `hints: list[str] = CANONICAL_KEYS[record.category]` per call (category-scoped, not full registry). (CTO R2 ACTION.)

### Phase 4 — DB + LLM-readability

11. **`schema/migrations/002-limits-expression-indexes.sql`** — 6 B-tree expression indexes (`compute_hours_per_month`, `rpd`, `grant_amount`, `storage_gb`, `context_window`, `investment_amount`) plus the `always_on` virtual column. SQLite + Postgres variants. (Architect R2 ACTION.)
12. **`schema/export_schema.py`** — emits `ProviderRecord.model_json_schema()` + each `*Limits.model_json_schema()` as `schema/provider-record.schema.json`. CI runs as part of lint. (Architect R4 ACTION.)
13. **API response envelope** carries `meta.$schema` pointing at the published JSON Schema. (Architect R4.)

### Phase 5 — frontend

14. **`LimitsView`** already renders any shape (shipped in PR #37). Optional follow-up: auto-generate label map from `model_json_schema()` `title` / `description` metadata. (Architect Appendix A2.)

---

## What's been ruled out

- **Per-category Pydantic subclasses on `ProviderRecord`** (discriminated union) — fails LLM-extractability for cross-category providers. (Architect R1.)
- **JSON-LD / RDF / triple-store** — over-engineering for this scale (55–500 records). Revisit only if project pivots to public knowledge graph. (Architect Appendix A3.)
- **schema.org / OpenMetadata / off-the-shelf catalog formats** — none cover free-tier + grant + credit + GPU multi-category data. (CTO B2.)

---

## Open items (need user decision)

1. **Approve hybrid + Phase 0–4 plan** as written. CTO O1 makes this a hard pre-condition: without explicit written approval, the architect can pivot mid-sprint to per-category subclasses and the timeline doubles.
2. **Phase 5 auto-label-map** — yes / no / defer. Marginal value; nice-to-have only if 4+ categories have populated limits in production.
3. **Budget** — solo founder evening time, 2-3 weeks. Hard cap?

---

## What happens if user approves

I (parent agent) execute Phase 0 immediately on the current branch (PR #37 still open or just-merged). Phases 1–4 land as separate PRs in dependency order. v0.2 agentic extractor work is BLOCKED on Phase 1–3 completion (CTO O2). Phase 5 deferred until the registry is proven in production.

## What happens if user defers

Current state holds: `limits: dict[str, Any]` flexible, no canonical-key registry, no typed registry, no round-trip test. The 4 cloud records (AWS / GCP / Azure / Oracle) and 10 enriched records keep their hand-shaped `limits` dicts. v0.2 agentic extractor proceeds without canonical-key hints — drift accepted as cost.
