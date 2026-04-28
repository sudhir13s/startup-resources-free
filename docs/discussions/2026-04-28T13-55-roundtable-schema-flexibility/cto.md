> **Revision of:** initial
> **Date / time:** 2026-04-28T13:55 (IST)
> **Source deliberation:** roundtable-schema-flexibility
> **Status:** AWAITING USER APPROVAL

---

# CTO Memo — Schema Flexibility Decision

## BLOCKERS

### B1 — OfferType enum divergence is live today, must fix before v0.2 extractor lands

[PERSONA: CTO | confidence: 9/10]

Observation 4773 confirmed `schema/records.py` carries `"free-tier"` (hyphen) while `backend/main.py` did not match at time of observation. Any hybrid approach that routes extractor output through `model_validate` will silently drop or reject records the moment the enum value mismatches. With 41 of 55 seed records having empty `limits`, and v0.2 extractor writing hundreds more, a silent coercion failure becomes a data-loss event — not a test failure. The `limits: dict[str, Any]` field is not the risk here; the enum inconsistency is.

Evidence that would move score down: confirm `backend/main.py` now mirrors the `OfferType` values from `schema/records.py` after the 2026-04-28 fix commit.

**Action:** before any schema change is discussed further, add a `pytest` round-trip test that model_validates a record from `seed.json` through both `schema/records.py` AND the API response model in `backend/main.py`. CI must catch this class of drift permanently.

---

### B2 — No off-the-shelf catalog standard fits; build is the only option, but the canonical-key registry needs a freeze trigger

[PERSONA: CTO | confidence: 8/10]

Web search and prior knowledge confirm no relevant open standard applies here. schema.org `PriceSpecification` covers e-commerce price points, not multi-category free-tier + grant + credit + GPU quota data. There is no "cloud provider free-tier catalog schema" standard. JSON-LD / OpenMetadata are metadata standards for data assets, not provider offerings. We build.

The risk: without a defined freeze trigger, the canonical-key registry becomes a living document that the v0.2 extractor never fully agrees with — because providers change what they publish. Declaring the registry "convention, not validation" defers this conflict until the frontend `LimitsView` has to render unknown keys gracefully, which it will — but it also means the extractor has no signal for when it missed a canonical key vs. when the provider genuinely doesn't publish that data.

Evidence that would move score down: a governance rule explicitly banning new canonical keys without a PR review.

**Action:** add a `CANONICAL_KEYS_REGISTRY.md` under `schema/` with a one-line description per key and a required PR review gate. The extractor uses this file as its extraction hint list.

---

## RECOMMENDATIONS

### R1 — Pydantic v2 `dict[str, Any]` is low-risk on this stack; no parallel TypedDicts needed

[PERSONA: CTO | confidence: 7/10]

Pydantic v2 `model_validate` handles `limits: dict[str, Any]` cleanly — no coercion surprises, no TypedDict maintenance. The field round-trips through FastAPI's JSON serialization without a custom serializer. SQLite stores it as a JSON string; the Postgres migration to `jsonb` with a GIN index is a one-line Alembic change when the time comes. The only real friction: `mypy --strict` will flag any code that tries to do `record.limits["requests_per_day"]` without a None-guard and cast. That's a good thing — it forces explicit narrowing at the frontend adapter layer rather than letting untyped dict access silently return `None` at runtime.

The hybrid proposal is stack-appropriate. Pure-rigid (per-category subclasses) would cost ~1 week to scaffold 12 discriminated-union variants plus a discriminator field, and would need to be rewritten every time a provider introduces a quota shape we didn't anticipate (common — providers change free tiers monthly per `scraping-ethics.md`). Pure-flexible (loose dict) gives up the extraction-hint benefit and makes the frontend `LimitsView` entirely ad-hoc.

**Action:** confirm `mypy --strict` is wired in CI against `schema/records.py` and `backend/main.py` before v0.2 ships. If not, add it — it's the only guard against `limits` access becoming a runtime type error at scale.

---

### R2 — Extractor prompt token cost is bounded, not a blocker, but needs a hard cap

[PERSONA: CTO | confidence: 6/10]

The canonical-key registry as an extraction hint will add ~200-400 tokens per extractor call (12 categories × ~5-10 keys each). At Groq's free tier (14,400 req/day, 30k tokens/min), the daily run processes ~200 providers — well within quota. The agentic-pipeline rule already hard-caps at 5,000 LLM calls per run, which is the real governor. The concern is prompt explosion if the canonical-key list is inlined verbatim for every provider, regardless of category. The fix is category-scoped injection: the extractor receives only the canonical keys for its provider's category, not the full 12-category registry.

**Action:** architect should spec the extractor prompt as `hints: list[str] = CANONICAL_KEYS[record.category]` — a 1-line filter that keeps prompt size proportional to category depth, not total registry size.

---

## OBSERVATIONS

### O1 — Solo founder timeline is realistic only if canonical-key spec is done before extractor work starts

[PERSONA: CTO | confidence: 5/10]

The hybrid proposal requires: (a) canonical-key registry authored per 12 categories, (b) `CANONICAL_KEYS_REGISTRY.md` merged, (c) extractor prompt updated, (d) `LimitsView` frontend updated to render unknown keys gracefully. In 2-3 weeks of evening time (~15-20 hours total), this is achievable IF the key sets are specced in one sitting (architect task, ~2 hours) and the extractor change is a prompt swap (1-2 hours). The risk is scope creep: if the architect proposes per-category Pydantic subclasses mid-sprint, the TypedDict maintenance alone adds a week.

**Action:** user explicitly approves the hybrid approach in writing before any code is touched, so the architect cannot pivot to pure-rigid mid-sprint.

---

### O2 — 41 empty `limits` records in seed.json are a gift, not a problem

[PERSONA: CTO | confidence: 5/10]

With 41 of 55 seed records having empty `limits`, the schema is still unfrozen. This is the ideal time to land the hybrid approach, because zero frontend code currently depends on specific `limits` key shapes. Post-v0.2, once the extractor has populated hundreds of records, refactoring the `limits` structure requires a migration. The window is now.

**Action:** block any v0.2 extractor work until the canonical-key registry is merged. The registry is the pre-condition.

---

## ASSIGNED ACTION

**One action before anything else:** add a `pytest` round-trip test that validates a representative seed record through `ProviderRecord.model_validate()` and through the FastAPI response serializer. This test catches the B1 OfferType divergence class permanently and proves the `limits: dict[str, Any]` field survives the full stack round-trip.

File: `tests/test_schema_roundtrip.py`. Target: green CI within the current sprint session.

---

## APPENDIX

### A1 — Future breaking change risk for third-party API consumers

[PERSONA: CTO | confidence: 3/10] [specialist-only]

If ResourceOS ever exposes a public API (the `FreeStackHub.com` angle), external consumers reading `limits` keys by name will break silently when canonical keys are renamed. At current scope (personal dashboard, no public API users), this is purely speculative. Note for when the public API scope is re-opened: version the canonical-key registry alongside the API version, and publish it as a JSON Schema document under `api/v1/schema/limits-registry.json`.

---

## GO / NO-GO: GO on hybrid

[PERSONA: CTO | confidence: 8/10]

Minimum viable cut: `limits: dict[str, Any]` in Pydantic, `CANONICAL_KEYS_REGISTRY.md` per 12 categories merged before extractor work begins, B1 round-trip test passing in CI. Full per-category subclass approach is a DEFER — trigger: only if query patterns after 200+ records show we need type-safe filter expressions on specific limit keys (e.g. `WHERE limits->>'requests_per_day' > 1000` in Postgres jsonb — achievable without subclasses via GIN index + jsonb operators).
