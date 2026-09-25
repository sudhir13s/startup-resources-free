"""Discovery: search + aggregator hop -> LLM rank -> Candidate rows.

Finds providers NOT yet in the catalog. Two feeds union together:
1. The search chain (`refresh/search.py`), queried per taxonomy category
   with India-primary phrasing.
2. An optional aggregator hop (curated list pages like
   grants.startupspeedrun.org) via `PoliteFetcher`.

Both feeds are deduped against every domain already known to the
catalog (from `source_urls` + `links` of every stored record) before
the LLM ranks what is left. Search or LLM failure is recorded in
`RunReport.errors` and never crashes the run — discovery is best-effort.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field

from domain.records import ProviderRecord
from domain.runs import Candidate
from refresh.fetch import PoliteFetcher
from refresh.search import AllSearchProvidersExhaustedError, SearchChain, SearchResult

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "discover.md"

DEFAULT_CATEGORIES: tuple[str, ...] = (
    "cloud",
    "gpu",
    "ai-api",
    "database",
    "storage",
    "startup-credit",
    "grant",
    "accelerator",
    "perk",
)

# Curated aggregator pages — one entry, expandable later. Politeness rules
# (robots, rate limit) apply via the shared PoliteFetcher.
AGGREGATORS: tuple[str, ...] = ("https://grants.startupspeedrun.org/",)


@dataclass
class DiscoveryOutcome:
    candidates: list[Candidate]
    queries_run: int = 0
    chain_exhausted: bool = False
    errors: list[str] = field(default_factory=list)


class _RankedCandidate(BaseModel):
    url: str
    title: str = ""
    category_guess: str = "cloud"
    score: float = 0.0
    reason: str = ""


class _DiscoveryResponse(BaseModel):
    candidates: list[_RankedCandidate] = Field(default_factory=list)


def registrable_domain(url: str) -> str:
    """Strip `www.` and compare apex — `docs.groq.com` and `groq.com` collapse
    together so we don't re-discover a provider we already track."""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def known_domains(records: Iterable[ProviderRecord]) -> set[str]:
    """Every domain already in the catalog, from source_urls and links."""
    domains: set[str] = set()
    for record in records:
        for url in record.source_urls:
            domains.add(registrable_domain(url))
        for link in record.links:
            domains.add(registrable_domain(link.url))
    return {d for d in domains if d}


def candidate_id(url: str) -> str:
    normalized = url.split("?")[0].rstrip("/")
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def build_queries(*, category: str) -> list[str]:
    """India-primary phrasings per category, using the current year."""
    year = datetime.now(tz=timezone.utc).year
    catalog: dict[str, list[str]] = {
        "cloud": [f"free tier cloud hosting {year}", "new free hosting platform for startups"],
        "gpu": ["free GPU cloud for ML", "free GPU notebook hosting"],
        "ai-api": ["free LLM API", "free vision LLM API", "free embedding API"],
        "database": ["free postgres database tier", "free serverless database"],
        "storage": ["free object storage", "free CDN with bandwidth"],
        "startup-credit": ["startup credits India", f"startup credit program {year}"],
        "grant": ["government grant startups India", "non-dilutive grant for startups India"],
        "accelerator": ["startup accelerator program India", f"accelerator with funding {year}"],
        "perk": ["free SaaS for startups India", "startup perks bundle"],
    }
    return catalog.get(category, [f"free {category} for startups India"])


def _dedupe(results: list[SearchResult], known: set[str], seen: set[str]) -> list[SearchResult]:
    out = []
    for r in results:
        d = r.domain()
        if not d or d in known or d in seen:
            continue
        seen.add(d)
        out.append(r)
    return out


async def _search_category(
    *,
    category: str,
    chain: SearchChain,
    known: set[str],
    max_results: int = 8,
    http_client: httpx.AsyncClient | None = None,
) -> tuple[list[SearchResult], int]:
    queries = build_queries(category=category)
    results: list[SearchResult] = []
    queries_run = 0
    seen: set[str] = set()

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        for q in queries:
            hits = await chain.search(q, max_results=max_results, client=client)
            queries_run += 1
            results.extend(_dedupe(hits, known, seen))
    finally:
        if owns_client:
            await client.aclose()
    return results, queries_run


async def _aggregator_hop(
    *, fetcher: PoliteFetcher, known: set[str]
) -> list[tuple[str, str, str]]:
    """Returns (url, title, category_hint) triples for links found on
    aggregator pages, deduped against `known` domains."""
    from selectolax.parser import HTMLParser

    out: list[tuple[str, str, str]] = []
    for source_url in AGGREGATORS:
        raw = await fetcher.fetch_raw(source_url)
        if raw is None or raw.status_code != 200:
            continue
        tree = HTMLParser(raw.text)
        base_host = urlparse(source_url).netloc.lower()
        seen: set[str] = set()
        for a in tree.css("a[href]"):
            href = (a.attributes.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:")):
                continue
            absolute = urljoin(source_url, href)
            host = urlparse(absolute).netloc.lower()
            domain = registrable_domain(absolute)
            if not host or host == base_host or domain in known or domain in seen:
                continue
            seen.add(domain)
            out.append((absolute, a.text(strip=True) or "", "grant"))
    return out


async def rank_candidates(
    candidates: list[tuple[str, str, str]], *, category: str, task_name: str
) -> list[Candidate]:
    """LLM-rank raw (url, title, category_hint) triples into Candidate rows."""
    import freellm

    if not candidates:
        return []
    lines = "\n".join(f"- {url} | title={title!r}" for url, title, _ in candidates[:50])
    messages = [
        {"role": "system", "content": _PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": f"CATEGORY: {category}\n\nCANDIDATES:\n{lines}"},
    ]
    result = await freellm.call_text(messages=messages, task_name=task_name, temperature=0, json_mode=True)
    payload = json.loads(result.content)
    parsed = _DiscoveryResponse.model_validate(payload)

    by_url = {url: (title, hint) for url, title, hint in candidates}
    out: list[Candidate] = []
    for ranked in parsed.candidates:
        if ranked.url not in by_url:
            continue
        title, hint = by_url[ranked.url]
        out.append(
            Candidate(
                candidate_id=candidate_id(ranked.url),
                url=ranked.url,
                domain=registrable_domain(ranked.url),
                title=ranked.title or title,
                snippet=ranked.reason,
                category_guess=ranked.category_guess or hint,
                reason=ranked.reason,
                score=ranked.score,
                found_via=f"discovery:{category}",
            )
        )
    return out


async def discover(
    *,
    chain: SearchChain,
    fetcher: PoliteFetcher,
    known: set[str],
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    max_per_category: int = 5,
) -> DiscoveryOutcome:
    """Full discovery sweep: aggregator hop once, then per-category search,
    LLM-ranked, top `max_per_category` kept per category."""
    outcome = DiscoveryOutcome(candidates=[])
    known = set(known)

    try:
        aggregator_hits = await _aggregator_hop(fetcher=fetcher, known=known)
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        aggregator_hits = []
        outcome.errors.append(f"aggregator hop failed: {exc}")

    for category in categories:
        raw: list[tuple[str, str, str]] = [
            (u, t, h) for u, t, h in aggregator_hits if h == category
        ]
        try:
            hits, queries_run = await _search_category(
                category=category, chain=chain, known=known, http_client=fetcher.http_client
            )
            outcome.queries_run += queries_run
            raw.extend((r.url, r.title, category) for r in hits)
        except AllSearchProvidersExhaustedError:
            outcome.chain_exhausted = True
            outcome.errors.append(f"search chain exhausted during discovery of {category}")

        if not raw:
            continue
        try:
            ranked = await rank_candidates(raw, category=category, task_name=f"discover:{category}")
        except Exception as exc:  # noqa: BLE001 — a bad LLM response must not crash discovery
            outcome.errors.append(f"ranking failed for {category}: {exc}")
            continue
        top = sorted(ranked, key=lambda c: c.score, reverse=True)[:max_per_category]
        outcome.candidates.extend(top)
        known.update(c.domain for c in top)

    return outcome
