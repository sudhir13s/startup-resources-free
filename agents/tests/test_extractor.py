"""extractor agent — round-trips raw HTML through the LLM into ProviderRecord."""

from __future__ import annotations

import asyncio
import json

from agents.extractor import _strip_html, extract_record


# ---------- pure helpers ----------


def test_strip_html_removes_scripts_styles_and_tags():
    html = (
        "<html><head><style>.x{color:red}</style>"
        "<script>alert(1)</script></head>"
        "<body><h1>Pricing</h1>  <p>Free   tier:   100 GB.</p></body></html>"
    )
    out = _strip_html(html)
    assert "alert" not in out
    assert ".x" not in out
    assert "Pricing" in out
    assert "100 GB" in out
    assert "  " not in out  # whitespace collapsed


# ---------- happy path ----------


def test_extract_record_happy_path(scripted_backend):
    payload = {
        "provider_id": "test-provider",
        "provider_name": "TestProvider",
        "category": "cloud",
        "headline": "Free hosting forever",
        "offer_summary": "100 GB bandwidth, unlimited static.",
        "offer_type": "free-tier",
        "currency": None,
        "credit_amount": None,
        "credit_duration_days": None,
        "limits": {"bandwidth_gb_per_month": 100},
        "quota_summary": "100 GB / mo",
        "duration_summary": "Always free",
        "region_summary": "Global",
        "eligibility_summary": "Any user",
        "access_method": "signup",
        "regions": ["global"],
        "user_types": ["any"],
        "company_age_max_years": None,
        "funding_max_usd": None,
        "restrictions": None,
        "geo_priority": "global-other",
        "india_accessible": True,
        "expiry_date": None,
        "notes": None,
    }
    scripted_backend.script("extractor", json.dumps(payload))

    record, confidence, error = asyncio.run(
        extract_record(
            page_text="<html><body>Free hosting forever. 100 GB.</body></html>",
            source_url="https://test.example/pricing",
            backend=scripted_backend,
        )
    )
    assert error is None
    assert record is not None
    # `medium` because the heuristic in agents.llm demotes when ANY field
    # is null (this happy-path payload has nullable fields = null).
    assert confidence in ("high", "medium")
    assert record.provider_id == "test-provider"
    assert record.provider_name == "TestProvider"
    assert record.category == "cloud"
    assert record.source_url == "https://test.example/pricing"
    assert record.source_method == "llm"
    assert record.parse_confidence == confidence
    assert record.limits == {"bandwidth_gb_per_month": 100}
    assert record.eligibility.regions == ["global"]


# ---------- error paths ----------


def test_extract_record_missing_required_field_is_low(scripted_backend):
    """Output without `provider_id` should yield low confidence + error."""
    payload = {
        "provider_name": "Anon",
        "category": "cloud",
        "offer_summary": "free stuff",
        "offer_type": "free-tier",
    }
    scripted_backend.script("extractor", json.dumps(payload))
    record, confidence, error = asyncio.run(
        extract_record(
            page_text="some text",
            source_url="https://x.test/",
            backend=scripted_backend,
        )
    )
    assert record is None
    assert confidence == "low"
    assert error is not None and "provider_id" in error


def test_extract_record_invalid_json_is_low(scripted_backend):
    """Garbled output should drop straight to low confidence."""
    scripted_backend.script("extractor", "not actually json {")
    record, confidence, error = asyncio.run(
        extract_record(
            page_text="text",
            source_url="https://x.test/",
            backend=scripted_backend,
        )
    )
    assert record is None
    assert confidence == "low"
    assert error is not None
    assert "json" in error or "schema" in error


def test_extract_record_strips_markdown_fence(scripted_backend):
    payload = {
        "provider_id": "render",
        "provider_name": "Render",
        "category": "cloud",
        "offer_summary": "Free 750 hrs/mo",
        "offer_type": "free-tier",
    }
    scripted_backend.script("extractor", "```json\n" + json.dumps(payload) + "\n```")
    record, confidence, error = asyncio.run(
        extract_record(
            page_text="text",
            source_url="https://render.com/pricing",
            backend=scripted_backend,
        )
    )
    assert error is None
    assert record is not None
    # Fenced output downgrades to medium per the heuristic.
    assert confidence == "medium"
    assert record.provider_id == "render"
