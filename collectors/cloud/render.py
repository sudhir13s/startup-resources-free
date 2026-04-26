"""Render.com free-tier collector.

Source: https://render.com/pricing
robots.txt: permits /pricing.

Render's pricing page exposes the "Free" plan with a 750 hr/mo
quota. Stable selector is the literal string '750 hours'.
"""

from __future__ import annotations

import re
from typing import Any

from collectors.base import BaseCollector

_HOURS_RE = re.compile(r"(\d{2,4})\s*(?:hours|hrs)\s*/\s*mo", re.IGNORECASE)


class RenderCollector(BaseCollector):
    provider_id = "render"
    provider_name = "Render"
    category = "hosting"
    source_url = "https://render.com/pricing"
    base_confidence = "medium"

    def extract_fields(self, body: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.provider_id,
            "name": self.provider_name,
            "category": self.category,
            "source_url": self.source_url,
            "parse_confidence": self.base_confidence,
            "offer_type": "always-free",
            "duration_summary": "Always free (sleeps)",
            "region_summary": "US / EU / SG",
            "eligibility_summary": "Any user",
            "use_case_tiers": ["hobby", "personal"],
            "india_accessible": True,
            "geo_priority": "global-other",
        }
        match = _HOURS_RE.search(body)
        if match:
            hrs = match.group(1)
            out["quota_summary"] = f"{hrs} hrs / mo"
            out["headline"] = (
                f"Web services with {hrs} hrs/mo. Free Postgres for 90 days."
            )
            out["free_tier_summary"] = (
                f"Free Web Services with {hrs} hrs/mo, free Postgres "
                "(1 GB, 90-day expiry), free Static Sites + Cron Jobs."
            )
        else:
            out["parse_confidence"] = "low"
            out["headline"] = "Web services + Postgres + Static Sites"
            out["free_tier_summary"] = "Free Web Services; verify quota manually."
            out["quota_summary"] = ""
        return out
