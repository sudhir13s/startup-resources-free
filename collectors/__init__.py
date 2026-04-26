"""Collectors — per-provider polite scrapers.

Each concrete collector subclasses `BaseCollector` and exposes:
  - provider_id     stable slug ("groq", "vercel", "supabase")
  - category        one of provider-schema.md CATEGORY_ENUM values
  - source_url      the public URL we fetch + extract from
  - robots_path     path to check in robots.txt (defaults to source_url path)
  - extract_fields()  parse FetchResult.text -> partial Provider dict

Collectors do NOT call LLMs. The LLM extractor (v0.2 with keys) reads
each FetchResult and fills in the structured fields. Collectors with
robust HTML structure (e.g. JSON LD on a pricing page) MAY return
fields directly from `extract_fields()` to bypass the LLM step;
otherwise they return only what they're sure about + parse_confidence.

Polite-by-default per `.claude/rules/project/scraping-ethics.md`:
  - identifiable User-Agent
  - robots.txt honored
  - 1 req / 30s per host (configurable upward only with reason)
  - ETag / Last-Modified caching skips body parse on 304
  - raw responses saved under data/raw/<provider>/<YYYY-MM-DD>.html
"""

from collectors.base import (
    BaseCollector,
    CollectorRegistry,
    FetchResult,
    PoliteClient,
)
from collectors.registry import REGISTRY

__all__ = [
    "BaseCollector",
    "CollectorRegistry",
    "FetchResult",
    "PoliteClient",
    "REGISTRY",
]
