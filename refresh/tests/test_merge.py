from __future__ import annotations

from datetime import date

from refresh.merge import merge


def test_should_keep_identity_fields_from_current_when_merging(groq_record):
    extracted = groq_record.model_copy(
        update={
            "provider_id": "totally-different-slug",
            "vendor": "Someone Else",
            "category": "database",
            "source_urls": ["https://evil.example.com"],
            "parse_confidence": "high",
        }
    )
    merged = merge(groq_record, extracted)
    assert merged.provider_id == groq_record.provider_id
    assert merged.vendor == groq_record.vendor
    assert merged.category == groq_record.category
    assert merged.source_urls == groq_record.source_urls


def test_should_keep_curated_fields_when_confidence_not_high(groq_record):
    extracted = groq_record.model_copy(
        update={"claim_steps": ["a completely new step"], "parse_confidence": "medium"}
    )
    merged = merge(groq_record, extracted)
    assert merged.claim_steps == groq_record.claim_steps


def test_should_overwrite_curated_fields_when_high_confidence_and_nonempty(groq_record):
    extracted = groq_record.model_copy(
        update={"claim_steps": ["new step one", "new step two"], "parse_confidence": "high"}
    )
    merged = merge(groq_record, extracted)
    assert merged.claim_steps == ["new step one", "new step two"]


def test_should_keep_curated_fields_when_high_confidence_but_extraction_empty(groq_record):
    extracted = groq_record.model_copy(update={"claim_steps": [], "parse_confidence": "high"})
    merged = merge(groq_record, extracted)
    assert merged.claim_steps == groq_record.claim_steps


def test_should_never_wipe_services_when_extraction_returns_empty(groq_record):
    extracted = groq_record.model_copy(update={"services": [], "parse_confidence": "high"})
    merged = merge(groq_record, extracted)
    assert merged.services == groq_record.services


def test_should_replace_services_when_extraction_returns_nonempty(groq_record):
    new_service = groq_record.services[0].model_copy(update={"name": "New Service"})
    extracted = groq_record.model_copy(update={"services": [new_service], "parse_confidence": "high"})
    merged = merge(groq_record, extracted)
    assert merged.services == [new_service]


def test_should_never_wipe_credits_when_extraction_returns_empty(sample_records):
    grant = next(r for r in sample_records if r.provider_id == "startup-india-seed-fund")
    extracted = grant.model_copy(update={"credits": [], "parse_confidence": "high"})
    merged = merge(grant, extracted)
    assert merged.credits == grant.credits


def test_should_stamp_fresh_timestamps_when_merging(groq_record):
    extracted = groq_record.model_copy(update={"parse_confidence": "medium"})
    merged = merge(groq_record, extracted)
    assert merged.last_verified_at == date.today()
    assert merged.source_method == "llm"
    assert merged.parse_confidence == "medium"


def test_should_return_extracted_as_is_when_no_current_record():
    from domain.records import ProviderRecord

    new_record = ProviderRecord(
        provider_id="brand-new",
        name="Brand New",
        vendor="Brand New Inc",
        category="cloud",
        source_urls=["https://brand-new.example.com"],
        offer_type="free-tier",
        headline="A new offer",
        use_case_tiers=["hobby"],
        parse_confidence="medium",
    )
    merged = merge(None, new_record)
    assert merged.provider_id == "brand-new"
    assert merged.source_method == "llm"
    assert merged.last_verified_at == date.today()
