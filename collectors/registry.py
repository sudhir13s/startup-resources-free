"""Collector registry — single source of truth for which collectors run.

Loads:
1. Hand-written collectors that beat the LLM (regex + JSON-LD) — registered explicitly.
2. The YAML catalog at `collectors/catalog.yaml` — every row becomes a
   GenericCollector that polite-fetches the URL and lets the LLM
   extractor handle the structure. Keeps adding a provider to a
   1-line YAML edit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from collectors.ai_apis.groq import GroqCollector
from collectors.base import CollectorRegistry
from collectors.cloud.render import RenderCollector
from collectors.cloud.vercel import VercelCollector
from collectors.generic import make_generic


CATALOG_PATH = Path(__file__).parent / "catalog.yaml"


def _hand_written_provider_ids() -> set[str]:
    """The provider_ids covered by hand-written collector files — we
    skip these in the YAML catalog so we don't double-register.
    """
    return {
        VercelCollector.provider_id,
        RenderCollector.provider_id,
        GroqCollector.provider_id,
    }


def _load_catalog_rows() -> list[dict[str, Any]]:
    """Flatten `catalog.yaml` ({category: [row,...]}) into a list of
    {provider_id, provider_name, category, source_url} dicts.
    """
    if not CATALOG_PATH.exists():
        return []
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    out: list[dict[str, Any]] = []
    for category, rows in raw.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "provider_id": row["provider_id"],
                    "provider_name": row["provider_name"],
                    "category": category,
                    "source_url": row["source_url"],
                }
            )
    return out


def _build() -> CollectorRegistry:
    reg = CollectorRegistry()
    # Hand-written first — typically more accurate than the LLM extractor.
    reg.register(VercelCollector())
    reg.register(RenderCollector())
    reg.register(GroqCollector())

    skip = _hand_written_provider_ids()
    for row in _load_catalog_rows():
        if row["provider_id"] in skip:
            continue
        reg.register(
            make_generic(
                provider_id=row["provider_id"],
                provider_name=row["provider_name"],
                category=row["category"],
                source_url=row["source_url"],
            )
        )
    return reg


REGISTRY = _build()
