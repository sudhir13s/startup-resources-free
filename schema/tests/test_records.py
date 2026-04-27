"""ProviderRecord canonical schema."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from schema.records import (
    Eligibility,
    ProviderRecord,
    record_from_seed,
)


SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed.json"


def _good_kwargs(**overrides):
    base = dict(
        id="abc123",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.com/pricing",
        offer_type="free-tier",
        offer_summary="Free Web Services with 750 hrs/month.",
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 27),
    )
    base.update(overrides)
    return base


# ---------- happy-path ----------


def test_minimum_required_fields_valid():
    record = ProviderRecord(**_good_kwargs())
    assert record.provider_id == "render"
    assert record.eligibility.regions == ["global"]
    assert record.use_case_tiers == []


def test_to_seed_shape_round_trip_keys():
    record = ProviderRecord(
        **_good_kwargs(
            quota_summary="750 hrs / mo",
            duration_summary="Always free",
            region_summary="US / EU / SG",
            eligibility_summary="Any user",
            use_case_tiers=["hobby", "personal"],
        )
    )
    seed = record.to_seed_shape()
    assert seed["id"] == "render"
    assert seed["use_case_tiers"] == ["hobby", "personal"]
    assert seed["last_verified_at"] == "2026-04-27"


# ---------- validators ----------


def test_currency_must_be_iso():
    with pytest.raises(ValidationError):
        ProviderRecord(**_good_kwargs(currency="dollars"))


def test_currency_uppercased():
    record = ProviderRecord(**_good_kwargs(currency="usd"))
    assert record.currency == "USD"


def test_source_url_must_be_http():
    with pytest.raises(ValidationError):
        ProviderRecord(**_good_kwargs(source_url="ftp://example.com"))


def test_stat_tile_over_40_chars_rejected():
    with pytest.raises(ValidationError):
        ProviderRecord(
            **_good_kwargs(
                quota_summary="x" * 41,
            )
        )


def test_stat_tile_30_to_40_accepted_for_legacy_seed_compat():
    # 32-char string should pass (existing seed has one).
    record = ProviderRecord(**_good_kwargs(eligibility_summary="x" * 32))
    assert len(record.eligibility_summary) == 32


# ---------- adapter ----------


def test_seed_adapter_inflates_every_existing_row():
    """Every row in data/seed.json must round-trip into ProviderRecord
    via record_from_seed without raising."""
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    inflated = [record_from_seed(row) for row in seed]
    assert len(inflated) == len(seed)
    # Spot-check first row preserves identity.
    first_row = seed[0]
    first_record = inflated[0]
    assert first_record.provider_id == first_row["id"]
    assert first_record.provider_name == first_row["name"]
    assert first_record.source_url == first_row["source_url"]


def test_seed_adapter_normalizes_pluralized_categories():
    seed_row = {
        "id": "test",
        "name": "T",
        "category": "databases",  # legacy plural
        "source_url": "https://t.example/",
        "offer_type": "free-tier",
        "free_tier_summary": "x",
        "use_case_tiers": [],
        "india_accessible": True,
        "geo_priority": "global-other",
        "parse_confidence": "high",
        "last_verified_at": "2026-04-27",
    }
    record = record_from_seed(seed_row)
    assert record.category == "database"  # canonical singular


def test_eligibility_default_open():
    record = ProviderRecord(**_good_kwargs())
    assert record.eligibility == Eligibility(regions=["global"], user_types=["any"])
