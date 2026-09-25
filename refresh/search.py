"""Search-API chain — quota-aware fallback over multiple free search APIs.

Mirrors `freellm/router.py`'s pattern for LLM rotation: try each provider
in order, fall through on rate-limit/auth/5xx, persist quota counters —
but for web search, and persisted through the repository's "search"
state namespace instead of a JSON file.

Provider chain (free-first):
1. Tavily       — TAVILY_API_KEY   (1,000 / mo free)
2. Exa.ai       — EXA_API_KEY      (1,000 / mo free)
3. Jina Search  — JINA_API_KEY     (large free quota)
4. Linkup       — LINKUP_API_KEY   (1,000 / mo free)
5. SerpAPI      — SERPAPI_API_KEY  (100 / mo free)

A provider missing its env var is dropped at chain-build time. If every
provider is unavailable or exhausted, `search()` raises
`AllSearchProvidersExhaustedError` — callers treat that as "no discovery
possible this run" and record it in `RunReport.errors`, never crash.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote, urlparse

import httpx

from storage.repository import Repository

STATE_NAMESPACE = "search"


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    score: float | None = None
    source_provider: str = ""

    def domain(self) -> str:
        return urlparse(self.url).netloc.lower()


class AllSearchProvidersExhaustedError(RuntimeError):
    def __init__(self, attempted: list[str]) -> None:
        self.attempted = attempted
        super().__init__(
            f"All search providers exhausted. Attempted: {', '.join(attempted) or '(none configured)'}"
        )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _current_month_key() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m")


@dataclass
class ProviderQuota:
    name: str
    month_key: str
    monthly_cap: int  # 0 = effectively unlimited
    requests_used: int = 0
    last_success_at: str | None = None
    last_failure_reason: str | None = None
    consecutive_failures: int = 0

    def is_exhausted(self) -> bool:
        return False if self.monthly_cap == 0 else self.requests_used >= self.monthly_cap

    def remaining(self) -> int:
        return 999_999 if self.monthly_cap == 0 else max(0, self.monthly_cap - self.requests_used)


@dataclass
class SearchQuotas:
    entries: dict[str, ProviderQuota] = field(default_factory=dict)

    def get(self, name: str, monthly_cap: int) -> ProviderQuota:
        current_month = _current_month_key()
        existing = self.entries.get(name)
        if existing is None or existing.month_key != current_month:
            self.entries[name] = ProviderQuota(name=name, month_key=current_month, monthly_cap=monthly_cap)
        return self.entries[name]

    def record_success(self, name: str, monthly_cap: int) -> None:
        q = self.get(name, monthly_cap)
        q.requests_used += 1
        q.last_success_at = _now_iso()
        q.consecutive_failures = 0

    def record_failure(self, name: str, monthly_cap: int, reason: str) -> None:
        q = self.get(name, monthly_cap)
        q.requests_used += 1
        q.consecutive_failures += 1
        q.last_failure_reason = reason[:200]

    def remaining_summary(self) -> dict[str, int]:
        return {name: q.remaining() for name, q in self.entries.items()}


def load_quotas(repository: Repository) -> SearchQuotas:
    raw = repository.get_state(STATE_NAMESPACE)
    entries = {key: ProviderQuota(**val) for key, val in raw.get("entries", {}).items()}
    return SearchQuotas(entries=entries)


def save_quotas(repository: Repository, quotas: SearchQuotas) -> None:
    from dataclasses import asdict

    repository.put_state(
        STATE_NAMESPACE, {"entries": {k: asdict(v) for k, v in quotas.entries.items()}}
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

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
        raise NotImplementedError


class TavilyProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="tavily", monthly_cap=1000, env_var="TAVILY_API_KEY")

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
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
        return [
            SearchResult(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                score=item.get("score"),
                source_provider=self.name,
            )
            for item in data.get("results", [])[:max_results]
        ]


class ExaProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="exa", monthly_cap=1000, env_var="EXA_API_KEY")

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
        resp = await client.post(
            "https://api.exa.ai/search",
            json={"query": query, "numResults": max_results, "type": "auto"},
            headers={"x-api-key": self.api_key()},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            SearchResult(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("text", ""),
                score=item.get("score"),
                source_provider=self.name,
            )
            for item in data.get("results", [])[:max_results]
        ]


class JinaProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="jina", monthly_cap=0, env_var="JINA_API_KEY")

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
        resp = await client.get(
            f"https://s.jina.ai/{quote(query)}",
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Accept": "application/json",
                "X-Retain-Images": "none",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else data
        out = [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("description", "") or item.get("content", "")[:300],
                source_provider=self.name,
            )
            for item in items[:max_results]
        ]
        return [r for r in out if r.url]


class LinkupProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="linkup", monthly_cap=1000, env_var="LINKUP_API_KEY")

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
        resp = await client.post(
            "https://api.linkup.so/v1/search",
            json={"q": query, "depth": "standard", "outputType": "searchResults"},
            headers={"Authorization": f"Bearer {self.api_key()}"},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("name", "") or item.get("title", ""),
                snippet=item.get("content", "") or item.get("snippet", ""),
                source_provider=self.name,
            )
            for item in data.get("results", [])[:max_results]
        ]
        return [r for r in out if r.url]


class SerpAPIProvider(_BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="serpapi", monthly_cap=100, env_var="SERPAPI_API_KEY")

    async def search(self, client: httpx.AsyncClient, query: str, *, max_results: int) -> list[SearchResult]:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": self.api_key(), "num": max_results, "engine": "google"},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        out = [
            SearchResult(
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                source_provider=self.name,
            )
            for item in data.get("organic_results", [])[:max_results]
        ]
        return [r for r in out if r.url]


_ALL_PROVIDER_CLASSES: tuple[type[_BaseProvider], ...] = (
    TavilyProvider,
    ExaProvider,
    JinaProvider,
    LinkupProvider,
    SerpAPIProvider,
)


# ---------- chain executor ----------


@dataclass
class SearchChain:
    providers: list[_BaseProvider]
    repository: Repository
    quotas: SearchQuotas
    persist_quotas: bool = True

    def names(self) -> list[str]:
        return [p.name for p in self.providers]

    async def search(
        self, query: str, *, max_results: int = 10, client: httpx.AsyncClient | None = None
    ) -> list[SearchResult]:
        """Try each provider in order; return the first successful result set.

        A zero-match success is still success — only network/auth/quota
        errors trigger fallthrough to the next provider.
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
                    continue
                attempted.append(p.name)
                try:
                    results = await p.search(client, query, max_results=max_results)
                    self.quotas.record_success(p.name, p.monthly_cap)
                    return results
                except httpx.HTTPStatusError as e:
                    last_error = e
                    self._handle_http_error(p, e)
                    continue
                except (httpx.HTTPError, ValueError) as e:
                    self.quotas.record_failure(p.name, p.monthly_cap, type(e).__name__)
                    last_error = e
                    continue
        finally:
            if self.persist_quotas:
                save_quotas(self.repository, self.quotas)
            if owns_client:
                await client.aclose()

        err = AllSearchProvidersExhaustedError(attempted)
        if last_error is not None:
            raise err from last_error
        raise err

    def _handle_http_error(self, provider: _BaseProvider, error: httpx.HTTPStatusError) -> None:
        code = error.response.status_code
        self.quotas.record_failure(provider.name, provider.monthly_cap, f"HTTP {code}")
        if code == 429:
            q = self.quotas.get(provider.name, provider.monthly_cap)
            q.requests_used = max(q.requests_used, q.monthly_cap or 1)


def get_chain(
    repository: Repository,
    *,
    providers: Iterable[_BaseProvider] | None = None,
    persist_quotas: bool = True,
) -> SearchChain:
    if providers is None:
        providers = [cls() for cls in _ALL_PROVIDER_CLASSES if cls().is_available()]
    quotas = load_quotas(repository)
    return SearchChain(
        providers=list(providers), repository=repository, quotas=quotas, persist_quotas=persist_quotas
    )


def chain_status(repository: Repository) -> dict[str, Any]:
    chain = get_chain(repository, persist_quotas=False)
    return {"providers_active": chain.names(), "remaining": chain.quotas.remaining_summary()}
