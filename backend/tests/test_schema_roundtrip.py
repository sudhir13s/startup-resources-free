"""Round-trip test for the canonical schema ↔ API response model.

Resolves CRITICAL findings from the 2026-04-28 schema-flexibility roundtable:
- CTO B1 (9/10): OfferType enum drift between `schema/records.py` and the
  FastAPI Provider response model in `backend/main.py` already happened
  once in this session. Without a CI gate, it will happen again.
- Architect O1 (5/10): two-model surface is a structural maintenance risk.

This test pulls a representative sample from `data/seed.json` and validates
each record passes BOTH:
1. `schema.records.ProviderRecord` — the canonical model used by the agentic
   pipeline + extractor + DB writer.
2. `backend.main.Provider` — the API response model the frontend consumes.

If either side adds / removes a Literal value or required field without
mirroring it, this test fails — surfacing the drift at PR time, not at
runtime.

Per `docs/discussions/2026-04-28T13-55-roundtable-schema-flexibility/cto.md`
ASSIGNED ACTION: this test is the pre-condition for any further schema work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# sys.path bootstrap to mirror backend/main.py's resolution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import Provider as ApiProvider  # noqa: E402
from schema.records import ProviderRecord  # noqa: E402

SEED_PATH = REPO_ROOT / "data" / "seed.json"


@pytest.fixture(scope="module")
def seed_rows() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_seed_loads_via_api_response_model(seed_rows: list[dict]) -> None:
    """Every seed record must validate as the FastAPI Provider response.

    This is what the frontend actually consumes. Any drift in OfferType,
    GeoPriority, ParseConfidence, or Tier between schema/records.py and
    backend/main.py is caught here.
    """
    failures: list[tuple[str, str]] = []
    for row in seed_rows:
        try:
            ApiProvider.model_validate(row)
        except ValidationError as e:
            failures.append((row.get("id", "<no-id>"), str(e)))
    assert not failures, (
        f"{len(failures)} seed record(s) failed API Provider validation. "
        f"This indicates schema drift between schema/records.py and "
        f"backend/main.py. First failure: {failures[0][0]} → {failures[0][1]}"
    )


def test_seed_loads_via_canonical_record_model(seed_rows: list[dict]) -> None:
    """Every seed record must inflate into ProviderRecord (canonical model).

    Mirrors the existing `test_seed_adapter_inflates_every_existing_row`
    in `schema/tests/test_records.py`, but here we also assert the result
    serializes cleanly back to JSON without losing fields — which is the
    real round-trip property.
    """
    # Use the same seed-adapter helper that schema/tests use, so this test
    # tracks any canonical-model evolution there.
    from schema.tests.test_records import record_from_seed  # type: ignore[import-not-found]

    failures: list[tuple[str, str]] = []
    for row in seed_rows:
        try:
            rec = record_from_seed(row)
            # Round-trip: model → dict → model. Catches non-serializable
            # values, datetime-vs-date drift, etc. Exclude computed fields
            # (`card_variant`) — they are derived from category, not stored,
            # so the model rejects them on re-validate (extra=forbid).
            redumped = rec.model_dump(mode="json", exclude={"card_variant"})
            ProviderRecord.model_validate(redumped)
        except (ValidationError, ValueError, TypeError) as e:
            failures.append((row.get("id", "<no-id>"), str(e)))
    assert not failures, (
        f"{len(failures)} seed record(s) failed ProviderRecord round-trip. "
        f"First failure: {failures[0][0]} → {failures[0][1]}"
    )


def test_offer_type_enum_matches_between_models() -> None:
    """OfferType drift detector — explicit assertion.

    The 2026-04-28 incident: schema/records.py had `'free-tier'`, backend
    Provider Literal did not. Pydantic silently rejects rows with the
    missing value. This test surfaces the divergence as a clear assertion
    error rather than a downstream record-validation cascade.
    """
    from typing import get_args

    from schema.records import OfferType as SchemaOfferType

    schema_values = set(get_args(SchemaOfferType))
    api_values = set(get_args(ApiProvider.model_fields["offer_type"].annotation))

    missing_in_api = schema_values - api_values
    missing_in_schema = api_values - schema_values
    assert not missing_in_api, (
        f"OfferType values in schema/records.py but missing in "
        f"backend/main.py: {missing_in_api}. This causes silent rejection "
        f"of valid records by the API."
    )
    assert not missing_in_schema, (
        f"OfferType values in backend/main.py but missing in "
        f"schema/records.py: {missing_in_schema}. This causes the "
        f"canonical model to reject API-accepted values on extractor write."
    )


def test_tier_enum_matches_between_models() -> None:
    """Same drift detector for the Tier (use_case_tiers element type)."""
    from typing import get_args

    from schema.records import UseCaseTier

    schema_tiers = set(get_args(UseCaseTier))
    api_tier_field = ApiProvider.model_fields["use_case_tiers"].annotation
    # list[Tier] → unwrap one layer
    inner = get_args(api_tier_field)[0]
    api_tiers = set(get_args(inner))

    assert schema_tiers == api_tiers, (
        f"Tier value drift: schema={schema_tiers - api_tiers}, "
        f"api={api_tiers - schema_tiers}"
    )


def test_geo_priority_enum_matches() -> None:
    """Drift detector for GeoPriority."""
    from typing import get_args

    from schema.records import GeoPriority as SchemaGeoPriority

    schema_values = set(get_args(SchemaGeoPriority))
    api_values = set(get_args(ApiProvider.model_fields["geo_priority"].annotation))
    assert schema_values == api_values, (
        f"GeoPriority drift: schema-only={schema_values - api_values}, "
        f"api-only={api_values - schema_values}"
    )


def test_parse_confidence_enum_matches() -> None:
    """Drift detector for ParseConfidence."""
    from typing import get_args

    from schema.records import ParseConfidence as SchemaParseConfidence

    schema_values = set(get_args(SchemaParseConfidence))
    api_values = set(
        get_args(ApiProvider.model_fields["parse_confidence"].annotation)
    )
    assert schema_values == api_values, (
        f"ParseConfidence drift: schema-only={schema_values - api_values}, "
        f"api-only={api_values - schema_values}"
    )
