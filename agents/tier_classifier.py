"""Tier-classifier agent — assigns use_case_tiers to a ProviderRecord.

Pure mutation step in the pipeline:

    record = await assign_tiers(record)
    # record.use_case_tiers + record.tier_fit_rationale set in place

If the LLM call fails or emits an unparseable response, the record's
existing tiers are kept (defaults to `[]` from extractor) and
`parse_confidence` is downgraded one notch (high→medium, medium→low).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from agents.llm import call_structured
from schema.records import ProviderRecord, UseCaseTier


_VALID_TIERS = {"hobby", "personal", "startup-mvp", "pre-seed", "seed", "series-a"}
_DEMOTE_CONFIDENCE = {"high": "medium", "medium": "low", "low": "low"}


class _TierResponse(BaseModel):
    use_case_tiers: list[str] = Field(default_factory=list)
    tier_fit_rationale: str | None = None

    @field_validator("use_case_tiers")
    @classmethod
    def _filter_valid(cls, v: list[str]) -> list[str]:
        # Drop unknown values silently; the LLM occasionally invents new
        # tiers ("startup-seed", "growth-stage"). We keep the canonical
        # set and downgrade confidence elsewhere.
        return [t for t in v if t in _VALID_TIERS]


async def assign_tiers(
    record: ProviderRecord,
    *,
    task_name: str = "assign-tiers",
    backend: Any = None,
) -> ProviderRecord:
    """Return a copy of `record` with `use_case_tiers` + `tier_fit_rationale`
    populated. On LLM failure: returns `record` unchanged with
    `parse_confidence` demoted one notch.
    """
    user_input = (
        f"PROVIDER: {record.provider_name}\n"
        f"CATEGORY: {record.category}\n"
        f"OFFER_TYPE: {record.offer_type}\n"
        f"OFFER_SUMMARY: {record.offer_summary}\n"
        f"QUOTA: {record.quota_summary}\n"
        f"DURATION: {record.duration_summary}\n"
        f"REGION: {record.region_summary}\n"
        f"NOTES: {record.notes or ''}\n"
        f"RESTRICTIONS: {record.restrictions or ''}\n"
    )
    sr = await call_structured(
        prompt_name="tier_classifier",
        user_input=user_input,
        response_model=_TierResponse,
        task_name=task_name,
        backend=backend,
        max_tokens=400,
        temperature=0.0,
    )
    if sr.parsed is None or not sr.parsed.use_case_tiers:
        # Demote confidence; keep whatever tiers the extractor already set.
        new_confidence = _DEMOTE_CONFIDENCE[record.parse_confidence]
        return record.model_copy(update={"parse_confidence": new_confidence})

    parsed = sr.parsed
    assert isinstance(parsed, _TierResponse)
    tiers: list[UseCaseTier] = parsed.use_case_tiers  # type: ignore[assignment]
    return record.model_copy(
        update={
            "use_case_tiers": tiers,
            "tier_fit_rationale": parsed.tier_fit_rationale,
        }
    )
