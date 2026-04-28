"""Search-chain executor — quota-aware fallback over multiple search APIs.

Mirrors the pattern in `freellm/router.py`: try each provider in order,
fall through to the next on rate-limit or exhaustion, persist quota
state across runs.

Provider chain (free-first):
1. Tavily       — TAVILY_API_KEY      (1,000 / mo free)
2. Exa.ai       — EXA_API_KEY          (1,000 / mo free)
3. Jina Search  — JINA_API_KEY         (~10M tokens / mo free, ~5,000 queries equiv)
4. Linkup       — LINKUP_API_KEY       (1,000 / mo free)
5. SerpAPI      — SERPAPI_API_KEY      (100 / mo free)

Each provider that lacks an API key is silently dropped at chain build
time. If ALL providers are missing keys → `chain.search()` raises
`AllSearchProvidersExhaustedError([])`. Callers handle that as
"no discovery possible this run".

ALL provider clients use httpx — no provider-specific SDK required.
This keeps requirements-agents.txt small and avoids version drift
across Tavily / Exa / etc. SDKs.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx

from agents import search_quotas

logger = logging.getLogger(__name__)


# ---------- result type ----------


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    score: float | None = None
    source_provider: str = ""  # which chain provider answered

    def domain(self) -> str:
        from urllib.parse import urlparse

        return urlparse(self.url).netloc.lower()


class AllSearchProvidersExhaustedError(RuntimeError):
    def __init__(self, attempted: list[str]):
        self.attempted = attempted
        super().__init__(
            f"All search providers exhausted. Attempted: {', '.join(attempted) or '(none — no API keys configured)'}"
        )


# ---------- provider implementations ----------


@dataclass
class _BaseProvider:
    name: str
    monthly_cap: int
    env_var: str

    def is_available(self) -> bool:
        return bool(os.environ.get(self.env_var))

    def api_key(self) -> str:
        return os.environ.get(self.env_var, "").strip()

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        raise NotImplementedError


class TavilyProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="tavily", monthly_cap=1000, env_var="TAVILY_API_KEY")

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        # https://docs.tavily.com/docs/rest-api/api-reference#endpoint-search
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.api_key(),
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get("results", [])[:max_results]:
            out.append(
                SearchResult(
                    url=item["url"],
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score"),
                    source_provider=self.name,
                )
            )
        return out


class ExaProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="exa", monthly_cap=1000, env_var="EXA_API_KEY")

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        # https://docs.exa.ai/reference/search
        resp = await client.post(
            "https://api.exa.ai/search",
            json={
                "query": query,
                "numResults": max_results,
                "type": "auto",
            },
            headers={"x-api-key": self.api_key()},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get("results", [])[:max_results]:
            out.append(
                SearchResult(
                    url=item["url"],
                    title=item.get("title", ""),
                    snippet=item.get("text", ""),
                    score=item.get("score"),
                    source_provider=self.name,
                )
            )
        return out


class JinaProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="jina", monthly_cap=0, env_var="JINA_API_KEY")  # ~unlimited

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        # https://jina.ai/reader#apiform — Search API: GET https://s.jina.ai/<query>
        resp = await client.get(
            f"https://s.jina.ai/{query}",
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Accept": "application/json",
                "X-Retain-Images": "none",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Jina returns {"data": [{"url", "title", "description", ...}, ...]}
        items = data.get("data", []) if isinstance(data, dict) else data
        out = []
        for item in items[:max_results]:
            out.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", "") or item.get("content", "")[:300],
                    source_provider=self.name,
                )
            )
        return [r for r in out if r.url]


class LinkupProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="linkup", monthly_cap=1000, env_var="LINKUP_API_KEY")

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        # https://docs.linkup.so/pages/api-reference/endpoint/post-search
        resp = await client.post(
            "https://api.linkup.so/v1/search",
            json={
                "q": query,
                "depth": "standard",
                "outputType": "searchResults",
            },
            headers={"Authorization": f"Bearer {self.api_key()}"},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get("results", [])[:max_results]:
            out.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("name", "") or item.get("title", ""),
                    snippet=item.get("content", "") or item.get("snippet", ""),
                    source_provider=self.name,
                )
            )
        return [r for r in out if r.url]


class SerpAPIProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="serpapi", monthly_cap=100, env_var="SERPAPI_API_KEY")

    async def search(
        self, client: httpx.AsyncClient, query: str, *, max_results: int = 10
    ) -> list[SearchResult]:
        # https://serpapi.com/search-api
        resp = await client.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": self.api_key(),
                "num": max_results,
                "engine": "google",
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get("organic_results", [])[:max_results]:
            out.append(
                SearchResult(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    score=None,
                    source_provider=self.name,
                )
            )
        return [r for r in out if r.url]


# ---------- chain executor ----------


@dataclass
class SearchChain:
    """Quota-aware fallback chain. Built via `get_chain()`."""

    providers: list[_BaseProvider]
    quotas: search_quotas.SearchQuotas = field(
        default_factory=search_quotas.SearchQuotas
    )
    persist_quotas: bool = True

    def names(self) -> list[str]:
        return [p.name for p in self.providers]

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> list[SearchResult]:
        """Try each provider in order. Return the first non-empty result set.

        Empty result on success (no matches) is still considered success —
        the chain does NOT fall through to the next provider just because
        a query matched zero pages. Only network / rate-limit / auth errors
        trigger fallthrough.
        """
        if not self.providers:
            raise AllSearchProvidersExhaustedError([])

        owns_client = client is None
        client = client or httpx.AsyncClient()
        attempted: list[str] = []
        last_error: BaseException | None = None
        try:
            for p in self.providers:
                if self.quotas.get(p.name, p.monthly_cap).is_exhausted():
                    logger.info("search:skip_exhausted", extra={"provider": p.name})
                    continue
                attempted.append(p.name)
                try:
                    results = await p.search(client, query, max_results=max_results)
                    self.quotas.record_success(p.name, p.monthly_cap)
                    logger.info(
                        "search:hit",
                        extra={
                            "provider": p.name,
                            "query": query[:80],
                            "result_count": len(results),
                        },
                    )
                    return results
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code
                    self.quotas.record_failure(
                        p.name, p.monthly_cap, f"HTTP {code}"
                    )
                    if code in (401, 403):
                        # Auth problem — drop this provider this run
                        logger.warning(
                            "search:auth_error",
                            extra={"provider": p.name, "status": code},
                        )
                        last_error = e
                        continue
                    if code == 429:
                        # Rate-limited — mark exhausted for the rest of the month
                        q = self.quotas.get(p.name, p.monthly_cap)
                        q.requests_used = max(q.requests_used, q.monthly_cap or 1)
                        logger.warning(
                            "search:rate_limited",
                            extra={"provider": p.name},
                        )
                        last_error = e
                        continue
                    # 5xx or other — record + fallthrough
                    last_error = e
                    continue
                except (httpx.HTTPError, ValueError) as e:
                    self.quotas.record_failure(
                        p.name, p.monthly_cap, type(e).__name__
                    )
                    last_error = e
                    continue
        finally:
            if self.persist_quotas:
                search_quotas.save(self.quotas)
            if owns_client:
                await client.aclose()

        err = AllSearchProvidersExhaustedError(attempted)
        if last_error is not None:
            raise err from last_error
        raise err


# ---------- factory ----------


_ALL_PROVIDER_CLASSES: tuple[type[_BaseProvider], ...] = (
    TavilyProvider,
    ExaProvider,
    JinaProvider,
    LinkupProvider,
    SerpAPIProvider,
)


def get_chain(
    *,
    providers: Iterable[_BaseProvider] | None = None,
    quotas: search_quotas.SearchQuotas | None = None,
    persist_quotas: bool = True,
) -> SearchChain:
    """Build the chain from env vars (or accept caller-supplied list).

    Providers without their `*_API_KEY` set are silently dropped. If
    NO providers are available, `chain.search()` will raise
    `AllSearchProvidersExhaustedError([])` immediately — callers handle
    that as "no discovery possible".
    """
    if providers is None:
        providers = [cls() for cls in _ALL_PROVIDER_CLASSES if cls().is_available()]
    quotas = quotas if quotas is not None else search_quotas.load()
    return SearchChain(
        providers=list(providers), quotas=quotas, persist_quotas=persist_quotas
    )


def chain_status(chain: SearchChain | None = None) -> dict[str, Any]:
    """For CLI / logs — what's the chain look like right now?"""
    chain = chain or get_chain(persist_quotas=False)
    return {
        "providers_active": chain.names(),
        "remaining": chain.quotas.remaining_summary(),
    }
