"""Change detector — pure code, no LLM.

Compares today's ProviderRecord against the most recent prior snapshot
of the SAME provider_id and produces a `ChangeReport` describing what
moved. The report is what feeds the dashboard's Changes tab and the
"Free Tier Shrunk" alert flow.

Detection levels:

- `unchanged`   — same offer; only metadata (scraped_at) differs.
- `metadata`    — non-substantive fields differ (notes, headline tweak).
- `improved`    — quota up, duration up, more regions, status -> active.
- `reduced`     — quota down, duration shortened, regions removed.
- `ended`       — `status` flipped to `ended` OR offer_type changed
                  to a less generous value.
- `new`         — no prior snapshot exists.

The classifier is conservative: when in doubt, label as `metadata` and
let the human verify queue surface it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from schema.records import ProviderRecord


ChangeSeverity = Literal["unchanged", "metadata", "improved", "reduced", "ended", "new"]


@dataclass
class ChangeReport:
    """One row's diff. Multiple records -> a list of these."""

    provider_id: str
    severity: ChangeSeverity
    changed_fields: list[str] = field(default_factory=list)
    summary: str = ""
    today_id: str | None = None
    yesterday_id: str | None = None


# Fields that are "substantive" — drift triggers a non-metadata diff.
_SUBSTANTIVE_FIELDS = (
    "offer_type",
    "offer_summary",
    "quota_summary",
    "duration_summary",
    "region_summary",
    "credit_amount",
    "credit_duration_days",
    "expiry_date",
    "status",
    "geo_priority",
    "use_case_tiers",
)

_NUMERIC_FIELDS = ("credit_amount", "credit_duration_days")


# Heuristic: words that signal direction in summary fields.
_REDUCTION_WORDS = re.compile(
    r"\b(reduced|removed|deprecated|ended|discontinued|paid|now\s+paid|sunset|smaller|less)\b",
    re.IGNORECASE,
)
_IMPROVEMENT_WORDS = re.compile(
    r"\b(increased|expanded|added|now\s+free|more|larger|generous)\b",
    re.IGNORECASE,
)


def _diff_fields(today: ProviderRecord, yesterday: ProviderRecord) -> list[str]:
    """List of substantive fields that differ between the two snapshots."""
    changed: list[str] = []
    for f in _SUBSTANTIVE_FIELDS:
        if getattr(today, f) != getattr(yesterday, f):
            changed.append(f)
    return changed


def _classify(today: ProviderRecord, yesterday: ProviderRecord) -> tuple[ChangeSeverity, str]:
    """Decide severity from the substantive diff. Returns (severity, summary)."""
    changed = _diff_fields(today, yesterday)
    if not changed:
        return "unchanged", "no substantive change"

    # Status flipped to ended/reduced -> dominant signal.
    if today.status == "ended":
        return "ended", "status -> ended"
    if today.status == "reduced":
        return "reduced", "status -> reduced"

    # Numeric direction: free credit / duration shifted.
    for f in _NUMERIC_FIELDS:
        if f in changed:
            t = getattr(today, f)
            y = getattr(yesterday, f)
            if t is None and y is not None:
                return "ended", f"{f}: {y} -> null"
            if t is not None and y is not None:
                if t > y:
                    return "improved", f"{f}: {y} -> {t}"
                if t < y:
                    return "reduced", f"{f}: {y} -> {t}"

    # offer_type direction. free-tier -> free-trial = reduction.
    rank = {
        "always-free": 5,
        "free-tier": 5,
        "free-quota": 4,
        "free-credits": 3,
        "free-trial": 2,
        "perk": 3,
        "grant": 4,
        "oss": 5,
    }
    if "offer_type" in changed:
        t_rank = rank.get(today.offer_type, 0)
        y_rank = rank.get(yesterday.offer_type, 0)
        if t_rank < y_rank:
            return "reduced", f"offer_type: {yesterday.offer_type} -> {today.offer_type}"
        if t_rank > y_rank:
            return "improved", f"offer_type: {yesterday.offer_type} -> {today.offer_type}"

    # Free-text summaries: scan for direction words.
    summary_text = " ".join(
        (
            today.offer_summary or "",
            today.quota_summary or "",
            today.duration_summary or "",
            today.region_summary or "",
        )
    )
    if _REDUCTION_WORDS.search(summary_text):
        return "reduced", "summary text indicates reduction"
    if _IMPROVEMENT_WORDS.search(summary_text):
        return "improved", "summary text indicates improvement"

    # Substantive diff with no clear direction = metadata-level.
    return "metadata", "fields changed: " + ", ".join(changed)


def diff_against_last(
    today: ProviderRecord,
    yesterday: ProviderRecord | None,
) -> ChangeReport:
    """Compare a single record vs its previous snapshot."""
    if yesterday is None:
        return ChangeReport(
            provider_id=today.provider_id,
            severity="new",
            changed_fields=[],
            summary="first time we've seen this provider",
            today_id=today.id,
            yesterday_id=None,
        )
    severity, summary = _classify(today, yesterday)
    return ChangeReport(
        provider_id=today.provider_id,
        severity=severity,
        changed_fields=_diff_fields(today, yesterday),
        summary=summary,
        today_id=today.id,
        yesterday_id=yesterday.id,
    )


def diff_batch(
    today_records: Iterable[ProviderRecord],
    yesterday_records: Iterable[ProviderRecord],
) -> list[ChangeReport]:
    """Diff a batch keyed by provider_id. Yesterday records missing from
    today are reported as `ended`. Today records missing from yesterday
    are reported as `new`.
    """
    y_by_id = {r.provider_id: r for r in yesterday_records}
    t_by_id = {r.provider_id: r for r in today_records}

    reports: list[ChangeReport] = []
    for pid, t in t_by_id.items():
        reports.append(diff_against_last(t, y_by_id.get(pid)))

    for pid, y in y_by_id.items():
        if pid not in t_by_id:
            reports.append(
                ChangeReport(
                    provider_id=pid,
                    severity="ended",
                    changed_fields=[],
                    summary="present yesterday, absent today",
                    today_id=None,
                    yesterday_id=y.id,
                )
            )
    return reports
