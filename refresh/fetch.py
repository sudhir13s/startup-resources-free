"""Polite HTTP fetching: robots.txt, per-host rate limit, conditional GET,
Jina Reader fallback for JS-rendered/blocked pages, and pricing-page follow.

Binds `.claude/rules/project/scraping-ethics.md`: honest User-Agent,
robots.txt honored per host, default 30s/host interval, timeout 30s,
retry only on 408/429/5xx/network with backoff+jitter, `Retry-After`
respected, ETag/Last-Modified conditional GET via the repository's
"http-cache" state namespace.
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from refresh.text import html_to_text
from storage.repository import Repository

USER_AGENT = "ResourceOS/2.0 (+https://github.com/sudhir13s/startup-resources-free)"
DEFAULT_MIN_INTERVAL_S = 30.0
DEFAULT_TIMEOUT_S = 30.0
MAX_RETRIES = 2
MAX_CONCURRENT_HOSTS = 5
JINA_READER_BASE = "https://r.jina.ai/"
SHORT_TEXT_THRESHOLD = 500
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# Pricing-page follow: path segments that signal the real free-tier specs
# live one hop away from a marketing landing page.
_PRICING_PATH_RE = re.compile(r"pricing|free|plans|startups|limits", re.IGNORECASE)
_PRICING_SIGNAL_RE = re.compile(
    r"(free\s+tier|free\s+forever|always\s+free|free\s+plan|"
    r"\$\s*0(\b|\s|$)|\d+\s*(GB|MB|TB|hrs?|hours|requests|req(/|\s|$)|tokens))",
    re.IGNORECASE,
)
MAX_FOLLOWS = 2

CACHE_NAMESPACE = "http-cache"


@dataclass
class FetchOutcome:
    """One page's fetch result, already reduced to readable text."""

    url: str
    text: str
    status_code: int | None
    not_modified: bool = False
    via_jina: bool = False
    robots_blocked: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.robots_blocked


def has_pricing_signal(text: str) -> bool:
    return bool(_PRICING_SIGNAL_RE.search(text or ""))


class PoliteFetcher:
    """Robots-aware, rate-limited, cache-conditional GET with a Jina fallback.

    One instance is shared across a whole refresh run so the per-host
    interval and robots cache apply globally, not per provider.
    """

    def __init__(
        self,
        repository: Repository,
        *,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        jina_api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._repo = repository
        self._min_interval_s = min_interval_s
        self._timeout_s = timeout_s
        self._jina_api_key = jina_api_key
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self._owns_client = client is None
        self._last_hit_monotonic: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._host_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HOSTS)

    @property
    def http_client(self) -> httpx.AsyncClient:
        """The underlying httpx client — reused by search calls so tests can
        inject one `httpx.MockTransport` for both fetching and searching."""
        return self._client

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _host(url: str) -> str:
        return urlparse(url).netloc.lower()

    async def _robots_allows(self, url: str) -> bool:
        host = self._host(url)
        if not host:
            return True
        if host not in self._robots_cache:
            self._robots_cache[host] = await self._load_robots(url, host)
        return self._robots_cache[host].can_fetch(USER_AGENT, url)

    async def _load_robots(self, url: str, host: str) -> RobotFileParser:
        robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
        parser = RobotFileParser()
        try:
            resp = await self._client.get(robots_url, timeout=self._timeout_s)
            parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except httpx.HTTPError:
            parser.parse([])
        return parser

    async def _wait_for_slot(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_hit_monotonic.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self._min_interval_s:
                await asyncio.sleep(self._min_interval_s - elapsed)
        self._last_hit_monotonic[host] = time.monotonic()

    def _cache_key(self, url: str) -> str:
        return url

    async def _conditional_get(self, url: str) -> httpx.Response:
        """One retried GET honoring ETag/Last-Modified + Retry-After."""
        cache = self._repo.get_state(CACHE_NAMESPACE)
        entry = cache.get(self._cache_key(url), {})
        headers: dict[str, str] = {}
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("last_modified"):
            headers["If-Modified-Since"] = entry["last_modified"]

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.get(url, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                await self._backoff(attempt)
                continue
            if resp.status_code not in _RETRYABLE_STATUS or attempt == MAX_RETRIES:
                return resp
            await self._backoff(attempt, retry_after=resp.headers.get("Retry-After"))
        if last_exc is not None:
            raise last_exc
        return resp  # unreachable in practice; satisfies type-checker

    @staticmethod
    async def _backoff(attempt: int, *, retry_after: str | None = None) -> None:
        if retry_after is not None:
            try:
                await asyncio.sleep(float(retry_after))
                return
            except ValueError:
                pass
        base = 2**attempt
        await asyncio.sleep(base + random.uniform(0, base))

    def _store_cache_headers(self, url: str, resp: httpx.Response) -> None:
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        if not etag and not last_modified:
            return
        cache = self._repo.get_state(CACHE_NAMESPACE)
        cache[self._cache_key(url)] = {"etag": etag, "last_modified": last_modified}
        self._repo.put_state(CACHE_NAMESPACE, cache)

    async def _via_jina(self, url: str) -> FetchOutcome:
        headers = {"X-Retain-Images": "none"}
        if self._jina_api_key:
            headers["Authorization"] = f"Bearer {self._jina_api_key}"
        try:
            resp = await self._client.get(f"{JINA_READER_BASE}{url}", headers=headers)
        except httpx.HTTPError as exc:
            return FetchOutcome(url=url, text="", status_code=None, error=str(exc))
        if resp.status_code != 200:
            return FetchOutcome(url=url, text="", status_code=resp.status_code, via_jina=True)
        return FetchOutcome(url=url, text=resp.text.strip(), status_code=200, via_jina=True)

    async def fetch_raw(self, url: str) -> httpx.Response | None:
        """Politely GET `url` (robots + rate limit honored) and return the
        raw response, or `None` if robots.txt disallows it or the request
        failed outright. Used by callers that need the HTML itself (link
        extraction) rather than cleaned text — still goes through the same
        politeness gate as `fetch()`.
        """
        if not await self._robots_allows(url):
            return None
        host = self._host(url)
        async with self._host_semaphore:
            await self._wait_for_slot(host)
            try:
                return await self._conditional_get(url)
            except (httpx.TimeoutException, httpx.NetworkError):
                return None

    async def fetch(self, url: str) -> FetchOutcome:
        """Fetch one URL: robots check, rate limit, conditional GET, clean
        the HTML to text, and fall back to Jina Reader when the result
        looks JS-rendered/blocked (short text or 403)."""
        if not await self._robots_allows(url):
            return FetchOutcome(url=url, text="", status_code=None, robots_blocked=True)

        host = self._host(url)
        async with self._host_semaphore:
            await self._wait_for_slot(host)
            try:
                resp = await self._conditional_get(url)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                return FetchOutcome(url=url, text="", status_code=None, error=str(exc))

        if resp.status_code == 304:
            return FetchOutcome(url=url, text="", status_code=304, not_modified=True)
        if resp.status_code != 200:
            if resp.status_code == 403:
                return await self._via_jina(url)
            return FetchOutcome(
                url=url, text="", status_code=resp.status_code, error=f"HTTP {resp.status_code}"
            )

        self._store_cache_headers(url, resp)
        text = html_to_text(resp.text)
        if len(text) < SHORT_TEXT_THRESHOLD:
            fallback = await self._via_jina(url)
            if fallback.ok and len(fallback.text) > len(text):
                return fallback
        return FetchOutcome(url=url, text=text, status_code=200)

    async def fetch_with_follow(self, url: str, *, max_follows: int = MAX_FOLLOWS) -> FetchOutcome:
        """Fetch `url`; if the landing page lacks pricing signal, try up to
        `max_follows` same-host links whose path looks pricing-related."""
        first = await self.fetch(url)
        if not first.ok or has_pricing_signal(first.text) or first.not_modified:
            return first

        candidates = await self._pricing_link_candidates(url)
        combined_text = first.text
        for candidate in candidates[:max_follows]:
            hop = await self.fetch(candidate)
            if not hop.ok:
                continue
            combined_text = f"{combined_text}\n\n---PAGE BREAK---\n\n{hop.text}"
            if has_pricing_signal(hop.text):
                break
        return FetchOutcome(url=url, text=combined_text, status_code=first.status_code)

    async def _pricing_link_candidates(self, url: str) -> list[str]:
        """Same-host links from `url`'s page whose path matches the pricing regex."""
        resp = await self.fetch_raw(url)
        if resp is None or resp.status_code != 200:
            return []
        from selectolax.parser import HTMLParser

        tree = HTMLParser(resp.text)
        host = self._host(url)
        seen: set[str] = set()
        out: list[str] = []
        for a in tree.css("a[href]"):
            href = (a.attributes.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            absolute = urljoin(url, href)
            if self._host(absolute) != host:
                continue
            path = urlparse(absolute).path
            if not _PRICING_PATH_RE.search(path):
                continue
            normalized = absolute.split("?")[0].rstrip("/")
            if normalized in seen or normalized == url.rstrip("/"):
                continue
            seen.add(normalized)
            out.append(absolute)
        return out
