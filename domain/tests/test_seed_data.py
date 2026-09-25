"""Contract tests for data/providers_seed.json — the v2 catalog seed.

Every record must validate as a ProviderRecord and satisfy the coverage and
honesty rules from provider-schema.md: unique ids, at least one source and
tier, short stat tiles, tier_fit_rationale on seed/series-a records, and
service-category coverage for the big multi-service cloud vendors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.records import ProviderRecord

SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "providers_seed.json"
TILE_MAX_CHARS = 30

MULTI_SERVICE_VENDORS = {
    "aws-free-tier": "AWS",
    "gcp-free-tier": "GCP",
    "azure-free": "Azure",
    "oracle-always-free": "Oracle",
    "cloudflare-free": "Cloudflare",
    "supabase": "Supabase",
}

NON_CATALOG_CATEGORIES = {"oss", "learning"}


@pytest.fixture(scope="module")
def raw_rows() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records(raw_rows: list[dict]) -> list[ProviderRecord]:
    return [ProviderRecord.model_validate(row) for row in raw_rows]


def by_id(records: list[ProviderRecord], provider_id: str) -> ProviderRecord:
    return next(r for r in records if r.provider_id == provider_id)


def test_should_validate_as_provider_record_when_loading_every_seed_row(raw_rows):
    errors = []
    for row in raw_rows:
        try:
            ProviderRecord.model_validate(row)
        except Exception as exc:  # noqa: BLE001 - collecting all failures for one clear report
            errors.append((row.get("provider_id", "<unknown>"), str(exc)))
    assert not errors, f"{len(errors)} seed rows failed validation: {errors}"


def test_should_have_unique_provider_ids_when_scanning_the_catalog(records):
    ids = [r.provider_id for r in records]
    duplicates = {pid for pid in ids if ids.count(pid) > 1}
    assert not duplicates, f"duplicate provider_id values: {duplicates}"


def test_should_have_at_least_one_source_url_when_scanning_the_catalog(records):
    missing = [r.provider_id for r in records if len(r.source_urls) < 1]
    assert not missing, f"records with no source_urls: {missing}"


def test_should_have_at_least_one_use_case_tier_when_scanning_the_catalog(records):
    missing = [r.provider_id for r in records if len(r.use_case_tiers) < 1]
    assert not missing, f"records with no use_case_tiers: {missing}"


def test_should_keep_stat_tiles_short_when_scanning_the_catalog(records):
    offenders = []
    for r in records:
        for field in ("quota_summary", "duration_summary", "region_summary", "eligibility_summary"):
            value = getattr(r, field)
            if len(value) > TILE_MAX_CHARS:
                offenders.append((r.provider_id, field, value))
    assert not offenders, f"stat tiles over {TILE_MAX_CHARS} chars: {offenders}"


def test_should_have_tier_fit_rationale_when_targeting_seed_or_series_a(records):
    missing = [
        r.provider_id
        for r in records
        if ({"seed", "series-a"} & set(r.use_case_tiers)) and not r.tier_fit_rationale
    ]
    assert not missing, f"seed/series-a records missing tier_fit_rationale: {missing}"


@pytest.mark.parametrize("provider_id,vendor_label", list(MULTI_SERVICE_VENDORS.items()))
def test_should_expose_database_and_storage_services_when_vendor_is_multi_service(
    records, provider_id, vendor_label
):
    record = by_id(records, provider_id)
    service_categories = {s.category for s in record.services}
    assert "database" in service_categories, f"{vendor_label} ({provider_id}) has no database service"
    assert "storage" in service_categories, f"{vendor_label} ({provider_id}) has no storage service"


def test_should_cover_every_resource_category_except_oss_and_learning(records):
    present = {r.category for r in records}
    from domain.taxonomy import RESOURCE_CATEGORIES

    required = set(RESOURCE_CATEGORIES) - NON_CATALOG_CATEGORIES
    missing = required - present
    assert not missing, f"resource categories with no record: {missing}"


def test_should_have_services_or_credits_when_offer_type_is_not_grant_or_oss(records):
    offenders = [
        r.provider_id
        for r in records
        if not r.services and not r.credits and r.offer_type not in {"grant", "oss"}
    ]
    assert not offenders, f"records with empty services AND empty credits (offer_type not grant/oss): {offenders}"


def test_should_merge_cloudflare_workers_and_r2_into_one_vendor_record(records):
    ids = {r.provider_id for r in records}
    assert "cloudflare-free" in ids
    assert "cloudflare-workers" not in ids
    assert "cloudflare-r2" not in ids
    # cloudflare-startups stays a separate startup-credit record.
    assert "cloudflare-startups" in ids


def test_should_sort_records_by_category_then_provider_id_when_reading_the_file(raw_rows):
    keys = [(row["category"], row["provider_id"]) for row in raw_rows]
    assert keys == sorted(keys)
