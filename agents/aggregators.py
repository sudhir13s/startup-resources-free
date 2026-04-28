"""Aggregator pages — curated lists where someone else already ranked
free-tier providers / grant programs / credits. We scrape these
recurringly and feed the extracted links into discovery as candidates,
alongside what the search-API chain returns.

Each aggregator has:
- a canonical URL
- a category hint (so the extractor knows what shape of record to expect)
- optional link-filter regex (skip social, contact, etc.)

Scraping is polite-fetch (1 req / 30 s / host) via the existing
`collectors.base.PoliteClient`. We never re-fetch within 7 days unless
the cron requests `--force`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser


@dataclass(frozen=True)
class AggregatorSource:
    url: str
    category_hint: str  # e.g. "grant", "startup-credit", "ai-api"
    notes: str = ""
    # Skip links matching any of these patterns (anchor text or href fragment).
    skip_patterns: tuple[str, ...] = (
        "twitter.com",
        "linkedin.com",
        "facebook.com",
        "youtube.com",
        "mailto:",
        "/about",
        "/contact",
        "/privacy",
        "/terms",
        "github.com/",  # generic GitHub links — usually social, not the actual provider site
    )


# Curated initial set. User-flagged (2026-04-28): grants.startupspeedrun.org.
# Add more here as we find them. Keep this list small + high-signal —
# every aggregator we add increases weekly-discovery's fetch volume.
AGGREGATORS: tuple[AggregatorSource, ...] = (
    AggregatorSource(
        url="https://grants.startupspeedrun.org/",
        category_hint="grant",
        notes="Curated startup grants + credits list (founder-maintained).",
    ),
    # Future candidates (commented out until vetted):
    # AggregatorSource(url="https://github.com/ripienaar/free-for-dev",
    #                  category_hint="cloud", notes="free-for-dev OSS list"),
    # AggregatorSource(url="https://github.com/cloudcommunity/Cloud-Free-Tier-Comparison",
    #                  category_hint="cloud", notes="Cloud free-tier comparison"),
)


_HREF_RE = re.compile(r"\bhttps?://[^\s\"'<>]+", re.IGNORECASE)


def extract_external_links(
    *,
    html: str,
    base_url: str,
    skip_patterns: Iterable[str] = (),
) -> list[str]:
    """Pull every external `<a href>` from the page.

    Filters out:
    - Links to the same host as `base_url` (these are nav, not providers).
    - Links matching any skip pattern (social, contact, etc.).
    - Fragment-only links (`#section`).

    Returns a deduplicated list, preserving order of first appearance.
    """
    base_host = urlparse(base_url).netloc.lower()
    skip = tuple(p.lower() for p in skip_patterns)
    seen: set[str] = set()
    out: list[str] = []

    tree = HTMLParser(html)
    for a in tree.css("a[href]"):
        raw = (a.attributes.get("href") or "").strip()
        if not raw or raw.startswith("#"):
            continue
        absolute = urljoin(base_url, raw)
        host = urlparse(absolute).netloc.lower()
        if not host or host == base_host:
            continue
        if any(p in absolute.lower() for p in skip):
            continue
        # Strip query strings + trailing slashes for dedupe
        normalized = absolute.split("?")[0].rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(absolute)
    return out


def hosts_in_aggregator_links(links: Iterable[str]) -> set[str]:
    """Return the set of distinct hosts across `links` — handy for
    dedupe against the existing catalog's known-domains set.
    """
    return {urlparse(u).netloc.lower() for u in links}
