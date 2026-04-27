"""GenericCollector — URL-only collector that defers to the LLM extractor.

For ~90% of providers, the pricing page is a hand-written marketing
document with no stable selectors. Writing a regex collector for each
one is brittle and dies the next time someone redesigns the site. The
LLM extractor (agents/extractor.py) reads the raw HTML directly and
emits a fully-typed ProviderRecord — same flow, no per-provider code.

`GenericCollector` plugs into the existing CollectorRegistry without
touching the chain logic. It:

1. Polite-fetches the URL (robots.txt + rate-limit + ETag / Last-Modified).
2. Saves raw HTML to `data/raw/<provider_id>/<date>.html`.
3. `extract_fields(body)` returns a SEED-shape stub so the heuristic
   pipeline path still works (mode=heuristic): the seed catalog has
   the curated baseline; the orchestrator's seed-merge fills in the
   rest. In `mode=auto` / `mode=llm`, the orchestrator IGNORES this
   stub and hands the raw body to `agents.extractor.extract_record`.

Adding a provider is a one-line `make_generic(...)` call in
`collectors/registry.py` — no new file required.
"""

from __future__ import annotations

from typing import Any, Iterable

from collectors.base import BaseCollector


class GenericCollector(BaseCollector):
    """One-class-fits-all polite-fetch collector.

    Subclassed-via-factory: `make_generic(provider_id, ...)` returns a
    fresh class with the constants set. Keeps the registry call sites
    short while preserving `BaseCollector.provider_id` etc. as class
    attributes (which the registry indexes on).
    """

    base_confidence = "medium"

    # The factory below sets these per instance.
    provider_id = "_generic"
    provider_name = "_generic"
    category = "cloud"
    source_url = "https://example.com"

    def extract_fields(self, body: str) -> dict[str, Any]:
        """Heuristic mode stub.

        We don't try to regex anything here — the seed.json baseline
        carries enough for the FE to render in heuristic mode. The
        LLM extractor handles the real work in mode=auto/llm.
        """
        return {
            "id": self.provider_id,
            "name": self.provider_name,
            "category": self.category,
            "source_url": self.source_url,
            # Pass-through so seed-merge keeps the rich fields seeded
            # for this provider.
            "parse_confidence": self.base_confidence,
        }


def make_generic(
    *,
    provider_id: str,
    provider_name: str,
    category: str,
    source_url: str,
    base_confidence: str = "medium",
) -> GenericCollector:
    """Build a GenericCollector instance with the given metadata.

    Returns a NEW subclass instance so each entry has distinct class
    attributes (BaseCollector reads them off the class, not the
    instance). This avoids registry-wide aliasing bugs that would
    otherwise come from sharing one class across N providers.
    """

    cls = type(
        f"GenericCollector_{provider_id.replace('-', '_')}",
        (GenericCollector,),
        {
            "provider_id": provider_id,
            "provider_name": provider_name,
            "category": category,
            "source_url": source_url,
            "base_confidence": base_confidence,
        },
    )
    return cls()


def make_many(rows: Iterable[dict[str, str]]) -> list[GenericCollector]:
    """Bulk-create from a list of `{provider_id, provider_name, category, source_url}` dicts."""
    return [
        make_generic(
            provider_id=row["provider_id"],
            provider_name=row["provider_name"],
            category=row["category"],
            source_url=row["source_url"],
            base_confidence=row.get("base_confidence", "medium"),
        )
        for row in rows
    ]
