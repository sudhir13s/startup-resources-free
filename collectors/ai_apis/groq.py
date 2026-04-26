"""Groq free-tier collector.

Source: https://console.groq.com/docs/rate-limits
robots.txt: permits /docs/.

The rate-limits page is mostly a static markdown render and lists
free-tier RPM / RPD per model. We grab the headline daily quota
for `llama-3.3-70b-versatile` as the canonical Groq number.
"""

from __future__ import annotations

import re
from typing import Any

from collectors.base import BaseCollector

# Look for "14,400 requests per day" or "14400 RPD" patterns near "llama-3"
_RPD_RE = re.compile(r"([\d,]+)\s*(?:requests\s*per\s*day|RPD)", re.IGNORECASE)


class GroqCollector(BaseCollector):
    provider_id = "groq"
    provider_name = "Groq"
    category = "ai-api"
    source_url = "https://console.groq.com/docs/rate-limits"
    base_confidence = "medium"

    def extract_fields(self, body: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.provider_id,
            "name": self.provider_name,
            "category": self.category,
            "source_url": self.source_url,
            "parse_confidence": self.base_confidence,
            "offer_type": "free-quota",
            "duration_summary": "Always free",
            "region_summary": "Global",
            "eligibility_summary": "Any developer with email",
            "use_case_tiers": ["hobby", "personal", "startup-mvp"],
            "india_accessible": True,
            "geo_priority": "global-other",
        }
        match = _RPD_RE.search(body)
        if match:
            rpd = match.group(1).replace(",", "")
            try:
                rpd_i = int(rpd)
                pretty = f"{rpd_i:,} req/day"
            except ValueError:
                pretty = f"{rpd} req/day"
            out["quota_summary"] = pretty
            out["headline"] = (
                f"Free LLM inference up to {pretty} across Llama-3 + Mixtral."
            )
            out["free_tier_summary"] = (
                f"Free tier: ~30 req/min, ~{pretty} on Llama-3.3-70B + others. "
                "Whisper STT free."
            )
        else:
            out["parse_confidence"] = "low"
            out["headline"] = "Very fast Llama / Mixtral / Whisper inference"
            out["free_tier_summary"] = (
                "Free tier with daily request cap; verify the exact RPD."
            )
            out["quota_summary"] = ""
        return out
