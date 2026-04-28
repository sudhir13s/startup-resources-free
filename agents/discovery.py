"""Discovery agent — finds NEW providers not yet in our catalog.

Two candidate sources:

1. **Search-API chain** (`agents.search.SearchChain`) — runs targeted
   queries with `-site:` exclusions of every domain we already know.
   Catches new launches, alternatives to incumbents, and India-specific
   programs the LLM wouldn't know from training.

2. **Aggregator pages** (`agents.aggregators.AGGREGATORS`) — scrapes
   curated lists like grants.startupspeedrun.org for outbound links,
   then dedupes against known domains.

Both feeds union together. The discovery LLM then ranks the merged
candidate set (via `agents/prompts/discovery.md`) and we keep the
top N per category.

Output: a list of `CandidateURL` records. Pipeline writes them to
`data/discovery_candidates/<date>.json` and proposes a PR adding them
to `collectors/catalog.yaml` for the next refresh cycle to extract.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from agents import aggregators
from agents.llm import call_structured
from agents.search import (
    AllSearchProvidersExhaustedError,
    SearchChain,
    SearchResult,
    get_chain,
)


logger = logging.getLogger(__name__)


# ---------- result types ----------


@dataclass
class CandidateURL:
    url: str
    title: str
    category: str
    score: float
    rationale: str
    discovered_via: str  # "search:tavily" / "aggregator:grants.startupspeedrun.org"

    def domain(self) -> str:
        return urlparse(self.url).netloc.lower()


@dataclass
class DiscoverySummary:
    started_at: str
    finished_at: str | None = None
    candidates: list[CandidateURL] = field(default_factory=list)
    skipped_known_domains: int = 0
    queries_run: int = 0
    aggregators_fetched: int = 0
    chain_exhausted: bool = False

    def to_dict(self) -> dict[str, Any]:
        out = {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "totals": {
                "candidates": len(self.candidates),
                "skipped_known_domains": self.skipped_known_domains,
                "queries_run": self.queries_run,
                "aggregators_fetched": self.aggregators_fetched,
                "chain_exhausted": self.chain_exhausted,
            },
            "candidates": [asdict(c) for c in self.candidates],
        }
        return out


# ---------- ranker (LLM step) ----------


class _RankedCandidate(BaseModel):
    url: str
    title: str = ""
    category: str = "cloud"
    score: float = 0.0
    rationale: str = ""


class _DiscoveryResponse(BaseModel):
    candidates: list[_RankedCandidate] = Field(default_factory=list)


# ---------- known-domain bookkeeping ----------


def collect_known_domains(*, seed_path: str | None = None) -> set[str]:
    """Every domain we already track — used as the search exclusion set.

    Sources merged:
    - `data/seed.json` (curated catalog, currently 51 rows)
    - `collectors/catalog.yaml` (URL list driving the cron)
    - The latest committed `data/snapshots/<date>.json` if present
    """
    from pathlib import Path

    domains: set[str] = set()

    repo_root = Path(__file__).resolve().parent.parent

    seed_p = Path(seed_path) if seed_path else repo_root / "data" / "seed.json"
    if seed_p.exists():
        rows = json.loads(seed_p.read_text(encoding="utf-8"))
        for row in rows:
            url = row.get("source_url", "")
            if url:
                domains.add(urlparse(url).netloc.lower())

    catalog_p = repo_root / "collectors" / "catalog.yaml"
    if catalog_p.exists():
        import yaml

        raw = yaml.safe_load(catalog_p.read_text(encoding="utf-8")) or {}
        for rows in raw.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and row.get("source_url"):
                    domains.add(urlparse(row["source_url"]).netloc.lower())

    snap_dir = repo_root / "data" / "snapshots"
    if snap_dir.exists():
        snaps = sorted(snap_dir.glob("*.json"))
        if snaps:
            for row in json.loads(snaps[-1].read_text(encoding="utf-8")):
                url = row.get("source_url", "")
                if url:
                    domains.add(urlparse(url).netloc.lower())

    return {d for d in domains if d}


# ---------- query builder ----------


def build_queries(
    *,
    category: str,
    excludes: set[str],
    max_excludes_per_query: int = 25,
) -> list[str]:
    """Build a small set of phrasings that cover NEW-provider discovery
    in `category`. Each query carries `-site:` exclusions for known
    domains (capped to keep query strings under most search APIs' limits).
    """
    # Take a deterministic slice of excludes — sorted for stable test output.
    excl = sorted(excludes)[:max_excludes_per_query]
    excl_clause = " ".join(f"-site:{d}" for d in excl)

    base = {
        "cloud": [
            f"free tier cloud hosting {datetime.now(tz=timezone.utc).year}",
            "new free hosting platform for startups",
            "free serverless platform alternatives",
        ],
        "gpu": [
            "free GPU cloud for ML",
            "free GPU notebook hosting",
        ],
        "ai-api": [
            "free LLM API",
            "free vision LLM API",
            "free embedding API",
            "free image generation API",
        ],
        "database": [
            "free postgres hosting",
            "free vector database",
            "free serverless database",
        ],
        "storage": [
            "free object storage",
            "free CDN with bandwidth",
        ],
        "auth": ["free auth as a service"],
        "observability": ["free APM logs metrics"],
        "startup-credit": [
            "startup credits cloud platform 2026",
            "new startup credit program 2026",
            "startup credits for Indian startups",
        ],
        "grant": [
            "non-dilutive grant for startups",
            "Indian government startup grant",
            "AI grant program for startups",
        ],
        "accelerator": [
            "startup accelerator program 2026",
            "Indian startup accelerator with funding",
        ],
        "perk": [
            "free SaaS for startups",
            "startup perks bundle",
        ],
    }
    phrasings = base.get(category, [f"free {category} for startups"])
    return [f"{q} {excl_clause}".strip() for q in phrasings]


# ---------- aggregator hop ----------


async def collect_from_aggregators(
    *,
    client: httpx.AsyncClient | None = None,
    known_domains: set[str] | None = None,
) -> tuple[list[CandidateURL], int]:
    """Walk every entry in `agents.aggregators.AGGREGATORS`, fetch each
    page once, extract external links, dedupe vs known domains.

    Returns (candidates, fetched_count).
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "ResourceOS-Discovery/0.1"},
    )
    known = known_domains if known_domains is not None else collect_known_domains()
    candidates: list[CandidateURL] = []
    fetched = 0
    try:
        for source in aggregators.AGGREGATORS:
            try:
                resp = await client.get(source.url)
                resp.raise_for_status()
                fetched += 1
            except httpx.HTTPError as e:
                logger.warning(
                    "discovery:aggregator_fetch_failed",
                    extra={"url": source.url, "error": str(e)},
                )
                continue
            links = aggregators.extract_external_links(
                html=resp.text,
                base_url=source.url,
                skip_patterns=source.skip_patterns,
            )
            seen_in_aggregator: set[str] = set()
            for link in links:
                domain = urlparse(link).netloc.lower()
                if not domain or domain in known or domain in seen_in_aggregator:
                    continue
                seen_in_aggregator.add(domain)
                candidates.append(
                    CandidateURL(
                        url=link,
                        title="",  # filled by ranker
                        category=source.category_hint,
                        score=0.5,  # neutral until LLM ranks
                        rationale=f"linked from {source.url}",
                        discovered_via=f"aggregator:{urlparse(source.url).netloc}",
                    )
                )
    finally:
        if owns_client:
            await client.aclose()
    return candidates, fetched


# ---------- search hop ----------


async def collect_from_search(
    *,
    category: str,
    chain: SearchChain | None = None,
    known_domains: set[str] | None = None,
    max_results_per_query: int = 8,
) -> tuple[list[CandidateURL], int]:
    """Run all queries for `category` through the search chain.

    Returns (candidates, queries_run). `queries_run` counts queries
    actually executed (not skipped because the chain was exhausted).
    """
    chain = chain or get_chain()
    known = known_domains if known_domains is not None else collect_known_domains()
    queries = build_queries(category=category, excludes=known)

    candidates: list[CandidateURL] = []
    queries_run = 0
    seen_domains_this_run: set[str] = set()

    async with httpx.AsyncClient() as client:
        for q in queries:
            try:
                results = await chain.search(
                    q, max_results=max_results_per_query, client=client
                )
                queries_run += 1
            except AllSearchProvidersExhaustedError:
                logger.warning(
                    "discovery:search_chain_exhausted", extra={"query": q[:80]}
                )
                break
            for r in _dedupe_results(results, known, seen_domains_this_run):
                candidates.append(
                    CandidateURL(
                        url=r.url,
                        title=r.title,
                        category=category,
                        score=r.score or 0.5,
                        rationale=(r.snippet or "")[:160],
                        discovered_via=f"search:{r.source_provider}",
                    )
                )
    return candidates, queries_run


def _dedupe_results(
    results: list[SearchResult],
    known_domains: set[str],
    seen_in_run: set[str],
) -> list[SearchResult]:
    out = []
    for r in results:
        d = r.domain()
        if not d or d in known_domains or d in seen_in_run:
            continue
        seen_in_run.add(d)
        out.append(r)
    return out


# ---------- ranker (calls the LLM via freellm) ----------


async def rank_candidates(
    candidates: list[CandidateURL],
    *,
    category: str,
    backend: Any = None,
    max_keep: int = 8,
) -> list[CandidateURL]:
    """Pass candidates through the LLM ranker (`prompts/discovery.md`).

    Returns the top `max_keep` ranked candidates with refreshed
    `score` + `rationale`. Falls back to score-sorted input on LLM
    parse failure.
    """
    if not candidates:
        return []
    user_input = (
        f"CATEGORY: {category}\n\n"
        f"CANDIDATES:\n"
        + "\n".join(
            f"- {c.url} | title={c.title!r} | discovered_via={c.discovered_via}"
            for c in candidates[:50]
        )
    )
    sr = await call_structured(
        prompt_name="discovery",
        user_input=user_input,
        response_model=_DiscoveryResponse,
        task_name="rank-discovery",
        backend=backend,
        max_tokens=1200,
        temperature=0.0,
    )
    if sr.parsed is None or not isinstance(sr.parsed, _DiscoveryResponse):
        # LLM failed — fall back to native score sort
        return sorted(candidates, key=lambda c: c.score, reverse=True)[:max_keep]

    by_url = {c.url: c for c in candidates}
    ranked: list[CandidateURL] = []
    for ranked_item in sr.parsed.candidates[:max_keep]:
        original = by_url.get(ranked_item.url)
        if original is None:
            continue
        ranked.append(
            CandidateURL(
                url=original.url,
                title=ranked_item.title or original.title,
                category=ranked_item.category or original.category,
                score=ranked_item.score,
                rationale=ranked_item.rationale,
                discovered_via=original.discovered_via,
            )
        )
    return ranked


# ---------- full sweep ----------


async def discover_all(
    *,
    categories: list[str] | None = None,
    chain: SearchChain | None = None,
    backend: Any = None,
    max_per_category: int = 5,
) -> DiscoverySummary:
    """End-to-end weekly-discovery sweep:

    1. Collect known domains (seed + catalog yaml + latest snapshot).
    2. Aggregator hop — scrape AGGREGATORS, dedupe vs known.
    3. Search hop — per-category queries with -site: exclusions.
    4. LLM rank — top N per category.
    5. Return aggregated summary; caller persists.
    """
    summary = DiscoverySummary(started_at=datetime.now(tz=timezone.utc).isoformat())
    categories = categories or [
        "cloud",
        "gpu",
        "ai-api",
        "database",
        "storage",
        "auth",
        "observability",
        "startup-credit",
        "grant",
        "accelerator",
        "perk",
    ]
    chain = chain or get_chain()
    known = collect_known_domains()

    # Aggregator hop runs once, results bucketed by category_hint.
    aggregator_cands, fetched = await collect_from_aggregators(known_domains=known)
    summary.aggregators_fetched = fetched
    by_category_aggr: dict[str, list[CandidateURL]] = {}
    for c in aggregator_cands:
        by_category_aggr.setdefault(c.category, []).append(c)

    for category in categories:
        # Aggregator + search candidates for this category
        cands = list(by_category_aggr.get(category, []))
        try:
            search_cands, qrun = await collect_from_search(
                category=category, chain=chain, known_domains=known
            )
            summary.queries_run += qrun
            cands.extend(search_cands)
        except AllSearchProvidersExhaustedError:
            summary.chain_exhausted = True

        if not cands:
            continue

        # Update known set immediately so next category doesn't re-find
        # the same domains.
        ranked = await rank_candidates(
            cands, category=category, backend=backend, max_keep=max_per_category
        )
        summary.candidates.extend(ranked)
        summary.skipped_known_domains += len(cands) - len(ranked)
        for c in ranked:
            known.add(c.domain())

    summary.finished_at = datetime.now(tz=timezone.utc).isoformat()
    return summary


def write_summary(summary: DiscoverySummary, *, out_dir: str | None = None) -> str:
    """Persist `summary` to `data/discovery_candidates/<date>.json`.

    Returns the file path written. The cron workflow then commits +
    proposes a PR adding the URLs to collectors/catalog.yaml.
    """
    from pathlib import Path

    base = (
        Path(out_dir)
        if out_dir
        else Path(__file__).resolve().parent.parent / "data" / "discovery_candidates"
    )
    base.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=timezone.utc).date().isoformat()
    path = base / f"{today}.json"
    path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return str(path)
