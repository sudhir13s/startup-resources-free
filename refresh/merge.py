"""Pure merge of a current record with a freshly extracted one.

The one rule that matters: refresh must never degrade curated data.
Identity is immutable, curated fields only move on a high-confidence
extraction, and list-shaped fields (services/credits) never get wiped
to empty just because the LLM missed them on one page.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from domain.records import ProviderRecord

# Curated fields a human (or a prior high-confidence pass) may have
# refined — only overwritten by a HIGH-confidence, non-empty extraction.
_CURATED_FIELDS = (
    "claim_steps",
    "gotchas",
    "links",
    "tier_fit_rationale",
    "use_case_tiers",
    "geo_priority",
    "notes",
)

# Identity fields that define WHICH offer this is — refresh can never
# rewrite these; they come from the current record, always.
_IDENTITY_FIELDS = ("provider_id", "vendor", "category", "source_urls")


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, str)):
        return len(value) == 0
    return False


def merge(current: ProviderRecord | None, extracted: ProviderRecord) -> ProviderRecord:
    """Combine `current` (may be None for a brand-new provider) with the
    LLM's `extracted` record, enforcing the never-degrade rules.

    - Identity fields: always from `current` (or `extracted` when there
      is no current record yet — a new provider has no identity to keep).
    - Curated fields: kept from `current` unless the extraction is
      `parse_confidence == "high"` AND supplies a non-empty value.
    - `services` / `credits`: taken from `extracted` only when non-empty
      — an extraction that found nothing never wipes what we already had.
    - Freshness (`last_verified_at`, `scraped_at`, `source_method`) is
      always stamped fresh; `parse_confidence` is always the extraction's
      own honest assessment.
    """
    if current is None:
        return extracted.model_copy(update=_freshness_update(extracted))

    updates: dict[str, object] = {field: getattr(current, field) for field in _IDENTITY_FIELDS}
    updates.update(_curated_updates(current, extracted))
    updates["services"] = extracted.services if extracted.services else current.services
    updates["credits"] = extracted.credits if extracted.credits else current.credits
    updates.update(_freshness_update(extracted))
    return extracted.model_copy(update=updates)


def _curated_updates(current: ProviderRecord, extracted: ProviderRecord) -> dict[str, object]:
    if extracted.parse_confidence != "high":
        return {field: getattr(current, field) for field in _CURATED_FIELDS}
    updates: dict[str, object] = {}
    for field in _CURATED_FIELDS:
        extracted_value = getattr(extracted, field)
        updates[field] = extracted_value if not _is_empty(extracted_value) else getattr(current, field)
    return updates


def _freshness_update(extracted: ProviderRecord) -> dict[str, object]:
    return {
        "last_verified_at": date.today(),
        "scraped_at": datetime.now(tz=timezone.utc),
        "source_method": "llm",
        "parse_confidence": extracted.parse_confidence,
    }
