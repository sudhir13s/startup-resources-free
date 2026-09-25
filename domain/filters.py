"""Catalog filtering and facet counts — shared by the API and tests."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from pydantic import BaseModel

from domain.records import ProviderRecord
from domain.taxonomy import (
    CONFIDENCE_RANK,
    CardVariant,
    GeoPriority,
    OfferType,
    ParseConfidence,
    UseCaseTier,
    normalize_category,
    normalize_offer_type,
)


class ProviderFilter(BaseModel):
    """Every filter the sidebar can set. Empty/None means 'no constraint'."""

    variant: CardVariant | None = None
    tiers: list[UseCaseTier] = []
    categories: list[str] = []
    offer_types: list[OfferType] = []
    geo: list[GeoPriority] = []
    min_confidence: ParseConfidence | None = None
    query: str | None = None


class Facets(BaseModel):
    """Counts per option, each computed with every OTHER active filter applied."""

    tiers: dict[str, int]
    categories: dict[str, int]
    offer_types: dict[str, int]
    geo: dict[str, int]


Predicate = Callable[[ProviderRecord], bool]


def _predicates(flt: ProviderFilter) -> dict[str, Predicate]:
    categories = {normalize_category(c) for c in flt.categories}
    offer_types = {normalize_offer_type(o) for o in flt.offer_types}
    query = (flt.query or "").strip().lower()
    preds: dict[str, Predicate] = {}
    if flt.variant:
        preds["variant"] = lambda r: r.card_variant == flt.variant
    if flt.tiers:
        preds["tiers"] = lambda r: bool(set(flt.tiers) & set(r.use_case_tiers))
    if categories:
        preds["categories"] = lambda r: bool(categories & set(r.categories))
    if offer_types:
        preds["offer_types"] = lambda r: r.offer_type in offer_types
    if flt.geo:
        preds["geo"] = lambda r: r.geo_priority in flt.geo
    if flt.min_confidence:
        threshold = CONFIDENCE_RANK[flt.min_confidence]
        preds["min_confidence"] = lambda r: CONFIDENCE_RANK[r.parse_confidence] >= threshold
    if query:
        preds["query"] = lambda r: query in _search_text(r)
    return preds


def _search_text(record: ProviderRecord) -> str:
    parts = [record.name, record.vendor, record.headline, *record.highlights]
    parts += [s.name for s in record.services]
    return " ".join(parts).lower()


def _passes(record: ProviderRecord, preds: dict[str, Predicate], skip: str | None = None) -> bool:
    return all(pred(record) for name, pred in preds.items() if name != skip)


def apply_filter(records: list[ProviderRecord], flt: ProviderFilter) -> list[ProviderRecord]:
    preds = _predicates(flt)
    return [r for r in records if _passes(r, preds)]


def facet_counts(records: list[ProviderRecord], flt: ProviderFilter) -> Facets:
    """Counts for each sidebar option, ignoring only that option's own filter."""
    preds = _predicates(flt)
    tiers: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    offer_types: Counter[str] = Counter()
    geo: Counter[str] = Counter()
    for record in records:
        if _passes(record, preds, skip="tiers"):
            tiers.update(record.use_case_tiers)
        if _passes(record, preds, skip="categories"):
            categories.update(record.categories)
        if _passes(record, preds, skip="offer_types"):
            offer_types[record.offer_type] += 1
        if _passes(record, preds, skip="geo"):
            geo[record.geo_priority] += 1
    return Facets(
        tiers=dict(tiers), categories=dict(categories),
        offer_types=dict(offer_types), geo=dict(geo),
    )
