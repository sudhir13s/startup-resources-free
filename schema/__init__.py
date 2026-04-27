"""Canonical record schema — single source of truth.

Used by:
- agents/extractor.py    -> emits ProviderRecord
- agents/tier_classifier -> mutates a ProviderRecord
- pipeline/run.py        -> persists ProviderRecord history
- backend/main.py        -> serializes ProviderRecord to API responses

Schema version pinned in `schema/VERSION` (single integer). Adding an
OPTIONAL field bumps the integer with no migration. Adding REQUIRED or
renaming demands a migration script in `schema/migrations/`.

See `.claude/rules/project/provider-schema.md` for the full spec.
"""

from __future__ import annotations

from schema.records import (
    AccessMethod,
    Category,
    Eligibility,
    GeoPriority,
    OfferType,
    ParseConfidence,
    ProviderRecord,
    SourceMethod,
    Status,
    UseCaseTier,
    record_from_seed,
)

__all__ = [
    "AccessMethod",
    "Category",
    "Eligibility",
    "GeoPriority",
    "OfferType",
    "ParseConfidence",
    "ProviderRecord",
    "SourceMethod",
    "Status",
    "UseCaseTier",
    "record_from_seed",
]
