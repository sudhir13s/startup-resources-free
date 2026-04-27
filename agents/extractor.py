"""Extractor agent — raw page text/HTML -> canonical ProviderRecord.

Workflow:

1. Caller hands `extract_record` the raw page text plus the source URL.
2. Internally we strip obvious junk (scripts, styles, repeated nav).
3. We call the LLM with `agents/prompts/extractor.md` + the cleaned text.
4. The LLM returns a JSON object matching `_ExtractedFields`.
5. We promote that into a full `ProviderRecord` (filling provenance:
   scraped_at, source_method, parse_confidence, source_url).

`source_method` is `llm` for extractor output. The pipeline can choose
to skip the extractor and emit `manual` records directly when the source
is an official API (no LLM needed).

Low-confidence outcomes:
- LLM emitted unparseable JSON          → returns (None, low)
- Required fields missing               → returns (record, low)
- Optional fields all null              → returns (record, medium)
- Clean parse, all fields populated     → returns (record, high)

Callers (`pipeline/run.py`) push `(parse_confidence == 'low')` records
through `agents.verifier.queue_low_confidence` for human review.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agents.llm import call_structured
from schema.records import (
    Eligibility,
    ParseConfidence,
    ProviderRecord,
)


# ---------- intermediate model for what the LLM returns ----------


class _ExtractedFields(BaseModel):
    """Mirror of the JSON shape the prompt asks the LLM for.

    All fields optional so a partial response still passes Pydantic and
    we can downgrade `parse_confidence` rather than reject the whole row.
    """

    model_config = ConfigDict(extra="allow")  # tolerate model verbosity

    provider_id: str | None = None
    provider_name: str | None = None
    category: str | None = None
    headline: str | None = None
    offer_summary: str | None = None
    offer_type: str | None = None
    currency: str | None = None
    credit_amount: float | None = None
    credit_duration_days: int | None = None
    limits: dict[str, Any] = Field(default_factory=dict)
    quota_summary: str | None = None
    duration_summary: str | None = None
    region_summary: str | None = None
    eligibility_summary: str | None = None
    access_method: str | None = None
    regions: list[str] = Field(default_factory=lambda: ["global"])
    user_types: list[str] = Field(default_factory=lambda: ["any"])
    company_age_max_years: int | None = None
    funding_max_usd: float | None = None
    restrictions: str | None = None
    geo_priority: str | None = None
    india_accessible: bool | None = None
    expiry_date: str | None = None  # ISO date string
    notes: str | None = None


# ---------- pre-processing ----------


_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Crude HTML cleaner — good enough for pricing pages.

    Pricing pages are almost always static markup; we just want the
    visible text. For complex SPAs we'd need a headless browser
    (covered by `collectors/base.py` upstream — extractor sees the
    rendered HTML).
    """
    text = _SCRIPT_RE.sub(" ", text)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


# ---------- record id ----------


def _stable_id(provider_id: str, source_url: str, scraped_at: datetime) -> str:
    """Stable but per-snapshot id.

    Same `(provider_id, source_url, scraped_at to second)` always
    produces the same id — useful for idempotent retries within a single
    pipeline run. New scrape on a later day produces a new id.
    """
    seed = f"{provider_id}|{source_url}|{scraped_at.replace(microsecond=0).isoformat()}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


# ---------- public api ----------


REQUIRED_FIELDS = (
    "provider_id",
    "provider_name",
    "category",
    "offer_summary",
    "offer_type",
)


async def extract_record(
    *,
    page_text: str,
    source_url: str,
    task_name: str = "extract-record",
    backend: Any = None,
    max_input_chars: int = 12_000,
) -> tuple[ProviderRecord | None, ParseConfidence, str | None]:
    """Run the extractor LLM call and inflate the result.

    Returns `(record, parse_confidence, error)`.

    - `record` is `None` only if the LLM output failed JSON parsing.
    - `parse_confidence` is `low|medium|high` per the heuristic in
      `agents/llm.py::call_structured` plus required-field checks here.
    - `error` is a short human-readable reason set when confidence is
      `low`; `None` otherwise.
    """
    cleaned = _strip_html(page_text)
    cleaned = _truncate(cleaned, max_input_chars)
    user_input = (
        f"SOURCE_URL: {source_url}\n\n"
        f"PAGE_TEXT:\n{cleaned}\n"
    )
    sr = await call_structured(
        prompt_name="extractor",
        user_input=user_input,
        response_model=_ExtractedFields,
        task_name=task_name,
        backend=backend,
        max_tokens=2000,
        temperature=0.0,
    )
    if sr.parsed is None:
        return None, "low", sr.error or "json-parse-failed"

    fields = sr.parsed
    assert isinstance(fields, _ExtractedFields)

    # Required-field check (independent of llm.py's heuristic).
    missing = [f for f in REQUIRED_FIELDS if getattr(fields, f) in (None, "")]
    if missing:
        return None, "low", f"missing required fields: {','.join(missing)}"

    # Promote the extracted fields into ProviderRecord.
    scraped_at = datetime.now(tz=timezone.utc)
    record = ProviderRecord(
        id=_stable_id(fields.provider_id, source_url, scraped_at),  # type: ignore[arg-type]
        provider_id=fields.provider_id,  # type: ignore[arg-type]
        provider_name=fields.provider_name,  # type: ignore[arg-type]
        category=fields.category,  # type: ignore[arg-type]
        source_url=source_url,
        offer_type=fields.offer_type,  # type: ignore[arg-type]
        offer_summary=fields.offer_summary,  # type: ignore[arg-type]
        headline=fields.headline,
        currency=fields.currency,
        credit_amount=fields.credit_amount,
        credit_duration_days=fields.credit_duration_days,
        limits=fields.limits,
        quota_summary=fields.quota_summary or "—",
        duration_summary=fields.duration_summary or "—",
        region_summary=fields.region_summary or "—",
        eligibility_summary=fields.eligibility_summary or "—",
        access_method=fields.access_method or "unknown",  # type: ignore[arg-type]
        eligibility=Eligibility(
            regions=fields.regions or ["global"],
            user_types=fields.user_types or ["any"],
            company_age_max_years=fields.company_age_max_years,
            funding_max_usd=fields.funding_max_usd,
        ),
        restrictions=fields.restrictions,
        geo_priority=fields.geo_priority or "global-other",  # type: ignore[arg-type]
        india_accessible=(
            fields.india_accessible
            if fields.india_accessible is not None
            else fields.geo_priority not in ("us-only", "eu-only")
        ),
        scraped_at=scraped_at,
        parse_confidence=sr.parse_confidence,
        source_method="llm",
        last_verified_at=date.today(),
        expiry_date=date.fromisoformat(fields.expiry_date)
        if fields.expiry_date
        else None,
        notes=fields.notes,
    )
    return record, sr.parse_confidence, None
