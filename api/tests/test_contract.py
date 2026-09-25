"""Parses the string-literal unions in `frontend/lib/types.ts` and asserts
they equal the `domain.taxonomy` tuples — the single source of truth the
Python side and the TypeScript side must never drift from.
"""

from __future__ import annotations

import re
from pathlib import Path

from domain.taxonomy import (
    GEO_PRIORITIES,
    OFFER_TYPES,
    USE_CASE_TIERS,
    FundCategory,
    PricingLayer,
    ResourceCategory,
)
from typing import get_args

TYPES_TS = Path(__file__).resolve().parent.parent.parent / "frontend" / "lib" / "types.ts"

# Matches `export type Name = "a" | "b" | ...;` possibly spanning lines,
# capturing everything up to the terminating semicolon.
_TYPE_ALIAS_RE = re.compile(r'export type (\w+)\s*=\s*([^;]+);', re.DOTALL)
_LITERAL_RE = re.compile(r'"([^"]+)"')


def _parse_type_aliases() -> dict[str, tuple[str, ...]]:
    """Every `export type X = "a" | "b"` union in types.ts, as a name -> values map.

    Aliases (e.g. `Category = ResourceCategory | FundCategory`) resolve by
    inlining any referenced alias names already collected, so a composed
    union still yields its full literal set.
    """
    source = TYPES_TS.read_text(encoding="utf-8")
    raw: dict[str, str] = {}
    for match in _TYPE_ALIAS_RE.finditer(source):
        raw[match.group(1)] = match.group(2)

    resolved: dict[str, tuple[str, ...]] = {}

    def resolve(name: str) -> tuple[str, ...]:
        if name in resolved:
            return resolved[name]
        body = raw[name]
        values: list[str] = []
        for part in body.split("|"):
            part = part.strip()
            literal = _LITERAL_RE.fullmatch(part)
            if literal:
                values.append(literal.group(1))
            elif part in raw:
                values.extend(resolve(part))
            # else: a non-literal, non-alias member (shouldn't occur for our enums)
        resolved[name] = tuple(values)
        return resolved[name]

    for name in raw:
        resolve(name)
    return resolved


def test_should_match_category_union_with_taxonomy():
    aliases = _parse_type_aliases()
    ts_categories = set(aliases["Category"])
    py_categories = set(get_args(ResourceCategory)) | set(get_args(FundCategory))
    assert ts_categories == py_categories


def test_should_match_offer_type_union_with_taxonomy():
    aliases = _parse_type_aliases()
    assert set(aliases["OfferType"]) == set(OFFER_TYPES)


def test_should_match_geo_priority_union_with_taxonomy():
    aliases = _parse_type_aliases()
    assert set(aliases["GeoPriority"]) == set(GEO_PRIORITIES)


def test_should_match_use_case_tier_union_with_taxonomy():
    aliases = _parse_type_aliases()
    assert set(aliases["UseCaseTier"]) == set(USE_CASE_TIERS)


def test_should_match_pricing_layer_union_with_taxonomy():
    aliases = _parse_type_aliases()
    assert set(aliases["PricingLayer"]) == set(get_args(PricingLayer))
