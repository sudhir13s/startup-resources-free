"""Field-level diff between two versions of the same offer. Pure code, no LLM."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

from domain.records import Limit, ProviderRecord, Service

ChangeSeverity = Literal["new", "improved", "reduced", "ended", "metadata"]

# Top-level fields whose change matters to a reader, with their default severity.
_TRACKED_FIELDS: dict[str, ChangeSeverity] = {
    "offer_type": "metadata",
    "headline": "metadata",
    "quota_summary": "metadata",
    "duration_summary": "metadata",
    "region_summary": "metadata",
    "eligibility_summary": "metadata",
    "geo_priority": "metadata",
    "use_case_tiers": "metadata",
    "expiry_date": "metadata",
    "after_free_period": "metadata",
}

_LESS_GENEROUS_OFFERS = {"free-trial", "free-credits"}


class FieldChange(BaseModel):
    """One reader-visible change, shown on the Changes page."""

    provider_id: str
    provider_name: str
    category: str
    field: str                    # "status", "services.Amazon RDS", "credits"
    old_value: Any | None = None
    new_value: Any | None = None
    severity: ChangeSeverity
    detected_at: datetime
    run_id: str | None = None


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _service_key(service: Service) -> str:
    return f"{service.name} ({service.pricing_layer})"


def _numeric_direction(old: Service, new: Service) -> ChangeSeverity:
    """Compare numeric limits with matching labels: any drop → reduced, else improved."""
    def key(limit: Limit) -> tuple[str, str | None, str | None]:
        return (limit.label, limit.unit, limit.period)

    old_values = {key(l): l.value for l in old.limits if isinstance(l.value, (int, float))}
    went_up = False
    for limit in new.limits:
        before = old_values.get(key(limit))
        if not isinstance(limit.value, (int, float)) or before is None:
            continue
        if isinstance(limit.value, bool) or isinstance(before, bool):
            continue
        if limit.value < before:
            return "reduced"
        if limit.value > before:
            went_up = True
    return "improved" if went_up else "metadata"


def _service_changes(old: ProviderRecord, new: ProviderRecord) -> list[tuple[str, Any, Any, ChangeSeverity]]:
    before = {_service_key(s): s for s in old.services}
    after = {_service_key(s): s for s in new.services}
    rows: list[tuple[str, Any, Any, ChangeSeverity]] = []
    for key in sorted(before.keys() - after.keys()):
        rows.append((f"services.{key}", before[key].summary, None, "reduced"))
    for key in sorted(after.keys() - before.keys()):
        rows.append((f"services.{key}", None, after[key].summary, "improved"))
    for key in sorted(before.keys() & after.keys()):
        old_s, new_s = before[key], after[key]
        if old_s == new_s:
            continue
        rows.append((f"services.{key}", old_s.summary, new_s.summary, _numeric_direction(old_s, new_s)))
    return rows


def _status_severity(new_status: str) -> ChangeSeverity:
    return {"ended": "ended", "reduced": "reduced", "active": "improved"}.get(new_status, "metadata")


def diff_records(
    old: ProviderRecord | None,
    new: ProviderRecord,
    *,
    run_id: str | None = None,
    detected_at: datetime | None = None,
) -> list[FieldChange]:
    """Changes from `old` to `new`. `old=None` yields a single `new` change."""
    when = detected_at or _now()

    def change(field: str, old_v: Any, new_v: Any, severity: ChangeSeverity) -> FieldChange:
        return FieldChange(
            provider_id=new.provider_id, provider_name=new.name, category=new.category,
            field=field, old_value=old_v, new_value=new_v, severity=severity,
            detected_at=when, run_id=run_id,
        )

    if old is None:
        return [change("record", None, new.headline, "new")]

    changes: list[FieldChange] = []
    if old.status != new.status:
        changes.append(change("status", old.status, new.status, _status_severity(new.status)))
    for field, severity in _TRACKED_FIELDS.items():
        old_v, new_v = getattr(old, field), getattr(new, field)
        if old_v == new_v:
            continue
        if field == "offer_type" and new_v in _LESS_GENEROUS_OFFERS and old_v not in _LESS_GENEROUS_OFFERS:
            severity = "reduced"
        changes.append(change(field, _jsonable(old_v), _jsonable(new_v), severity))
    old_credit = sum(c.amount or 0 for c in old.credits)
    new_credit = sum(c.amount or 0 for c in new.credits)
    if old.credits != new.credits:
        severity: ChangeSeverity = "metadata"
        if new_credit < old_credit:
            severity = "reduced"
        elif new_credit > old_credit:
            severity = "improved"
        changes.append(change("credits", old_credit or None, new_credit or None, severity))
    for field, old_v, new_v, severity in _service_changes(old, new):
        changes.append(change(field, old_v, new_v, severity))
    return changes


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return list(value)
    return value
