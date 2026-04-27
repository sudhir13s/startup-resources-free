"""tier_classifier agent — populates use_case_tiers + rationale."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

from agents.tier_classifier import assign_tiers
from schema.records import ProviderRecord


def _record(**overrides) -> ProviderRecord:
    base = dict(
        id="x",
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
        scraped_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="llm",
        last_verified_at=date(2026, 4, 27),
    )
    base.update(overrides)
    return ProviderRecord(**base)


def test_assign_tiers_populates_record(scripted_backend):
    scripted_backend.script(
        "tier_classifier",
        json.dumps(
            {
                "use_case_tiers": ["hobby", "personal"],
                "tier_fit_rationale": "Free 750 hrs covers always-on for one personal site.",
            }
        ),
    )
    base = _record(use_case_tiers=[])
    out = asyncio.run(assign_tiers(base, backend=scripted_backend))
    assert out.use_case_tiers == ["hobby", "personal"]
    assert out.tier_fit_rationale is not None
    assert "Free 750 hrs" in out.tier_fit_rationale


def test_assign_tiers_filters_invalid_tiers(scripted_backend):
    """LLM occasionally invents tiers — they get dropped silently."""
    scripted_backend.script(
        "tier_classifier",
        json.dumps(
            {
                "use_case_tiers": ["hobby", "growth-stage", "personal"],
                "tier_fit_rationale": "fits hobby + personal",
            }
        ),
    )
    base = _record(use_case_tiers=[])
    out = asyncio.run(assign_tiers(base, backend=scripted_backend))
    assert out.use_case_tiers == ["hobby", "personal"]


def test_assign_tiers_demotes_confidence_on_garbage(scripted_backend):
    """Unparseable LLM output keeps existing tiers + demotes confidence."""
    scripted_backend.script("tier_classifier", "not json")
    base = _record(use_case_tiers=["hobby"], parse_confidence="high")
    out = asyncio.run(assign_tiers(base, backend=scripted_backend))
    assert out.use_case_tiers == ["hobby"]
    assert out.parse_confidence == "medium"


def test_assign_tiers_demotes_confidence_on_empty_tiers(scripted_backend):
    scripted_backend.script(
        "tier_classifier",
        json.dumps({"use_case_tiers": [], "tier_fit_rationale": ""}),
    )
    base = _record(use_case_tiers=["hobby"], parse_confidence="medium")
    out = asyncio.run(assign_tiers(base, backend=scripted_backend))
    assert out.parse_confidence == "low"
