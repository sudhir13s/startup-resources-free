"""change_detector — pure code, no LLM."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from agents.change_detector import diff_against_last, diff_batch
from schema.records import ProviderRecord


def _record(**overrides) -> ProviderRecord:
    """Build a minimal ProviderRecord with sane defaults."""
    base = dict(
        id="test-id",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.com/pricing",
        offer_type="free-tier",
        offer_summary="Free Web Services with 750 hrs/month.",
        quota_summary="750 hrs / mo",
        duration_summary="Always free (sleeps)",
        region_summary="US / EU / SG",
        eligibility_summary="Any user",
        india_accessible=True,
        geo_priority="global-other",
        use_case_tiers=["hobby", "personal"],
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 27),
    )
    base.update(overrides)
    return ProviderRecord(**base)


# ---------- single diff ----------


def test_no_prior_snapshot_is_new():
    today = _record()
    report = diff_against_last(today, None)
    assert report.severity == "new"
    assert report.changed_fields == []
    assert report.yesterday_id is None


def test_unchanged_when_substantive_fields_match():
    today = _record(scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc))
    yesterday = _record(scraped_at=datetime(2026, 4, 26, tzinfo=timezone.utc))
    report = diff_against_last(today, yesterday)
    assert report.severity == "unchanged"


def test_quota_summary_change_with_reduction_word_is_reduced():
    yesterday = _record(quota_summary="750 hrs / mo")
    today = _record(quota_summary="500 hrs / mo (reduced)")
    report = diff_against_last(today, yesterday)
    assert report.severity == "reduced"


def test_credit_amount_drop_is_reduced():
    yesterday = _record(
        offer_type="free-credits", credit_amount=300.0, currency="USD"
    )
    today = _record(
        offer_type="free-credits", credit_amount=100.0, currency="USD"
    )
    report = diff_against_last(today, yesterday)
    assert report.severity == "reduced"
    assert "credit_amount" in report.changed_fields


def test_credit_amount_rise_is_improved():
    yesterday = _record(
        offer_type="free-credits", credit_amount=100.0, currency="USD"
    )
    today = _record(
        offer_type="free-credits", credit_amount=500.0, currency="USD"
    )
    report = diff_against_last(today, yesterday)
    assert report.severity == "improved"


def test_offer_type_downgrade_is_reduced():
    yesterday = _record(offer_type="free-tier")
    today = _record(offer_type="free-trial")
    report = diff_against_last(today, yesterday)
    assert report.severity == "reduced"


def test_status_ended_dominates():
    yesterday = _record(status="active")
    today = _record(status="ended")
    report = diff_against_last(today, yesterday)
    assert report.severity == "ended"


# ---------- batch diff ----------


def test_batch_handles_new_existing_and_dropped():
    yesterday = [
        _record(provider_id="render"),
        _record(provider_id="vercel"),
        _record(provider_id="dropped"),
    ]
    today = [
        _record(provider_id="render"),  # unchanged
        _record(provider_id="vercel", quota_summary="200 GB / mo"),  # metadata-ish
        _record(provider_id="newcomer"),  # new
    ]
    reports = diff_batch(today, yesterday)
    by_pid = {r.provider_id: r for r in reports}

    assert by_pid["render"].severity == "unchanged"
    assert by_pid["vercel"].severity in ("metadata", "improved", "reduced")
    assert by_pid["newcomer"].severity == "new"
    assert by_pid["dropped"].severity == "ended"


@pytest.mark.parametrize(
    "today_status,yesterday_status,expected",
    [
        ("active", "active", "unchanged"),
        ("ended", "active", "ended"),
        ("reduced", "active", "reduced"),
    ],
)
def test_status_transitions(today_status, yesterday_status, expected):
    today = _record(status=today_status)
    yesterday = _record(status=yesterday_status)
    report = diff_against_last(today, yesterday)
    assert report.severity == expected
