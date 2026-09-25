"""Domain contract tests: record shape, filters, facets, diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.changes import diff_records
from domain.filters import ProviderFilter, apply_filter, facet_counts
from domain.records import Limit, ProviderRecord

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample_records.json"


@pytest.fixture
def records() -> list[ProviderRecord]:
    return [ProviderRecord.model_validate(row) for row in json.loads(FIXTURE.read_text())]


def by_id(records: list[ProviderRecord], provider_id: str) -> ProviderRecord:
    return next(r for r in records if r.provider_id == provider_id)


def test_should_include_service_categories_when_computing_categories(records):
    aws = by_id(records, "aws-free-tier")
    assert aws.categories == ["cloud", "database"]


def test_should_match_database_filter_when_only_a_service_is_a_database(records):
    matched = apply_filter(records, ProviderFilter(categories=["databases"]))
    assert [r.provider_id for r in matched] == ["aws-free-tier"]


def test_should_split_views_when_filtering_by_variant(records):
    funds = apply_filter(records, ProviderFilter(variant="funds"))
    assert [r.provider_id for r in funds] == ["startup-india-seed-fund"]


def test_should_ignore_own_facet_when_counting_categories(records):
    facets = facet_counts(records, ProviderFilter(variant="resource", categories=["database"]))
    assert facets.categories["ai-api"] == 1
    assert facets.tiers == {"hobby": 1, "personal": 1, "startup-mvp": 1, "pre-seed": 1}


def test_should_normalize_legacy_slugs_when_validating(records):
    row = by_id(records, "groq").to_storage()
    row["category"] = "hosting"
    row["offer_type"] = "always-free"
    record = ProviderRecord.from_storage(row)
    assert (record.category, record.offer_type) == ("cloud", "free-tier")


def test_should_revalidate_when_dump_includes_derived_fields(records):
    aws = by_id(records, "aws-free-tier")
    dumped = aws.model_dump(mode="json")
    assert "categories" in dumped
    assert ProviderRecord.model_validate(dumped) == aws


def test_should_reject_record_when_tile_too_long(records):
    row = by_id(records, "groq").to_storage()
    row["quota_summary"] = "x" * 41
    with pytest.raises(ValidationError):
        ProviderRecord.from_storage(row)


def test_should_derive_india_access_from_geo(records):
    assert by_id(records, "groq").india_accessible is True
    us_only = by_id(records, "groq").model_copy(update={"geo_priority": "us-only"})
    assert us_only.india_accessible is False


def test_should_report_new_when_no_previous_version(records):
    changes = diff_records(None, by_id(records, "groq"))
    assert [c.severity for c in changes] == ["new"]


def test_should_report_reduced_when_a_limit_drops(records):
    old = by_id(records, "groq")
    service = old.services[0]
    smaller = service.model_copy(
        update={"limits": [Limit(label="Requests", value=500, unit="requests", period="day")]}
    )
    new = old.model_copy(update={"services": [smaller]})
    changes = diff_records(old, new)
    assert [(c.field, c.severity) for c in changes] == [
        ("services.Llama 3.3 70B Versatile (quota)", "reduced")
    ]


def test_should_report_nothing_when_only_freshness_changes(records):
    old = by_id(records, "groq")
    new = old.model_copy(update={"parse_confidence": "high"})
    assert diff_records(old, new) == []
    assert old.content_fingerprint() == new.content_fingerprint()
