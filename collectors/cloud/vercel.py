"""Vercel free-tier collector.

Source: https://vercel.com/pricing — last reviewed 2026-04-26.
robots.txt: https://vercel.com/robots.txt — public-tier docs are
allowed; we hit the user-facing pricing page only.

Heuristic field extraction is intentionally minimal — Vercel's
pricing page is heavy with React-hydrated content, so we only
mark `parse_confidence: medium` and let the LLM extractor (v0.2)
fill in numeric quotas. Without LLM keys, this collector saves
the raw HTML and emits a stub record.
"""

from __future__ import annotations

import re
from typing import Any

from collectors.base import BaseCollector

_GB_BANDWIDTH_RE = re.compile(r"(\d{2,4})\s*GB[^.]*bandwidth", re.IGNORECASE)


class VercelCollector(BaseCollector):
    provider_id = "vercel"
    provider_name = "Vercel"
    category = "hosting"
    source_url = "https://vercel.com/pricing"
    base_confidence = "medium"

    def extract_fields(self, body: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.provider_id,
            "name": self.provider_name,
            "category": self.category,
            "source_url": self.source_url,
            "parse_confidence": self.base_confidence,
            "offer_type": "always-free",
            "duration_summary": "Always free (Hobby)",
            "region_summary": "Global",
            "eligibility_summary": "Personal use only",
            "use_case_tiers": ["hobby", "personal"],
            "india_accessible": True,
            "geo_priority": "global-other",
        }
        match = _GB_BANDWIDTH_RE.search(body)
        if match:
            gb = match.group(1)
            out["quota_summary"] = f"{gb} GB / mo"
            out["headline"] = (
                f"Frontend hosting + edge functions. "
                f"{gb} GB bandwidth/mo on Hobby."
            )
            out["free_tier_summary"] = (
                f"Hobby: unlimited static, {gb} GB bandwidth/mo, "
                "serverless + edge functions, preview deploys."
            )
        else:
            # Markup changed; fall back without the quota number.
            out["parse_confidence"] = "low"
            out["headline"] = (
                "Frontend hosting + edge functions on Vercel's global network."
            )
            out["free_tier_summary"] = "Hobby plan; verify the bandwidth quota manually."
            out["quota_summary"] = ""
        return out
