"""List/detail/facets over the provider catalog — the `/api/providers*` logic."""

from __future__ import annotations

from domain.filters import Facets, ProviderFilter, apply_filter, facet_counts
from domain.records import ProviderRecord
from domain.taxonomy import CATEGORIES, GEO_PRIORITIES, normalize_category
from storage.repository import Repository

# Sort order for the catalog grid: India-first, then the rest of the geo
# ladder, then alphabetical within each geo bucket.
_GEO_ORDER: dict[str, int] = {geo: index for index, geo in enumerate(GEO_PRIORITIES)}


class UnknownCategoryError(ValueError):
    """A requested category slug is not in the taxonomy, even after alias normalization."""


def _sort_key(record: ProviderRecord) -> tuple[int, str]:
    return (_GEO_ORDER.get(record.geo_priority, len(_GEO_ORDER)), record.name.lower())


def list_providers(
    repository: Repository, flt: ProviderFilter
) -> tuple[int, list[ProviderRecord], Facets]:
    """Return (total-in-variant, sorted+filtered items, facet counts).

    `total` counts every record in the requested variant (or all records
    when no variant is set) — the frontend contract distinguishes this
    from `matched`, the post-filter count.
    """
    all_records = repository.list_providers()
    variant_records = (
        [r for r in all_records if r.card_variant == flt.variant] if flt.variant else all_records
    )
    matched = sorted(apply_filter(variant_records, flt), key=_sort_key)
    facets = facet_counts(variant_records, flt)
    return len(variant_records), matched, facets


def get_provider_detail(
    repository: Repository, provider_id: str
) -> tuple[ProviderRecord, list, list[ProviderRecord]] | None:
    """Return (record, history, related-same-vendor) or None when unknown."""
    record = repository.get_provider(provider_id)
    if record is None:
        return None
    history = repository.history(provider_id)
    related = [
        other
        for other in repository.list_providers()
        if other.vendor == record.vendor and other.provider_id != provider_id
    ]
    return record, history, related


def normalize_categories(categories: list[str]) -> list[str]:
    """Map legacy/plural slugs to canonical ones; raise if any is still unknown."""
    normalized = [normalize_category(c) for c in categories]
    unknown = [c for c in normalized if c not in CATEGORIES]
    if unknown:
        raise UnknownCategoryError(f"unknown category slug(s): {', '.join(unknown)}")
    return normalized
