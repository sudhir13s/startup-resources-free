"""Polite collector base class + HTTP client."""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "data" / "raw"

DEFAULT_USER_AGENT = (
    "ResourceOS-Scraper/0.2 "
    "(+https://github.com/sudhir13s/startup-resources-free; "
    "contact: sudhir.13singh@gmail.com)"
)
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RATE_LIMIT_S = 30.0  # 1 req / 30s / host


# ============================================================
# Fetch result
# ============================================================


@dataclass
class FetchResult:
    """What a collector emits from `fetch()`."""

    provider_id: str
    source_url: str
    status_code: int
    text: str  # response body (may be empty if 304 not modified)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    fetched_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    raw_path: Path | None = None  # where the raw HTML was saved

    @property
    def is_ok(self) -> bool:
        return self.status_code in (200, 304)


# ============================================================
# Polite HTTP client
# ============================================================


class PoliteClient:
    """httpx.AsyncClient wrapper enforcing per-host rate limit + UA + robots.txt.

    A single PoliteClient instance is shared across collectors in a run
    so rate limits are enforced globally per host (not per collector).
    """

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limit_s: float = DEFAULT_RATE_LIMIT_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: httpx.AsyncClient | None = None,
    ):
        self.user_agent = user_agent
        self.rate_limit_s = rate_limit_s
        self.timeout_s = timeout_s
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )
        self._owns_client = client is None
        self._last_hit_at: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "PoliteClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    @staticmethod
    def host_of(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower()

    async def _wait_for_rate_limit(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_hit_at.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self.rate_limit_s:
                await asyncio.sleep(self.rate_limit_s - elapsed)
        self._last_hit_at[host] = time.monotonic()

    async def is_allowed_by_robots(self, url: str) -> bool:
        host = self.host_of(url)
        if not host:
            return True
        if host not in self._robots_cache:
            robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
            rp = RobotFileParser()
            try:
                resp = await self._client.get(robots_url, timeout=self.timeout_s)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # No robots.txt or unreachable -> permissive default.
                    rp.parse([])
            except httpx.HTTPError:
                rp.parse([])
            self._robots_cache[host] = rp
        rp = self._robots_cache[host]
        return rp.can_fetch(self.user_agent, url)

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        """Polite GET with rate limiting + If-None-Match / If-Modified-Since."""
        host = self.host_of(url)
        await self._wait_for_rate_limit(host)
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        resp = await self._client.get(url, headers=headers)
        return resp.status_code, resp.text, dict(resp.headers)


# ============================================================
# Cache for ETag / Last-Modified per provider
# ============================================================


def _cache_path(provider_id: str) -> Path:
    return PROJECT_ROOT / "data" / "raw" / provider_id / "_cache.json"


def load_etag_cache(provider_id: str) -> tuple[str | None, str | None]:
    p = _cache_path(provider_id)
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("etag"), data.get("last_modified")
    except (OSError, json.JSONDecodeError):
        return None, None


def save_etag_cache(provider_id: str, etag: str | None, last_modified: str | None) -> None:
    p = _cache_path(provider_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"etag": etag, "last_modified": last_modified}, indent=2),
        encoding="utf-8",
    )


def save_raw(provider_id: str, body: str, snap_date: date | None = None) -> Path:
    snap_date = snap_date or datetime.now(tz=timezone.utc).date()
    out = PROJECT_ROOT / "data" / "raw" / provider_id / f"{snap_date.isoformat()}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out


# ============================================================
# Base collector
# ============================================================


class BaseCollector(ABC):
    provider_id: str
    provider_name: str
    category: str
    source_url: str
    # If subclass parses fields heuristically (no LLM), set base_confidence
    # accordingly. LLM extractor downstream may upgrade this.
    base_confidence: str = "medium"

    @abstractmethod
    def extract_fields(self, body: str) -> dict[str, Any]:
        """Best-effort field extraction from response body.

        Return a partial dict matching `provider-schema.md` fields. Empty
        keys are filled in by the LLM extractor. Implementations should
        prefer 'medium' confidence when they extract via brittle CSS
        selectors and 'high' only when reading an official API.
        """

    async def collect(self, client: PoliteClient) -> FetchResult:
        if not await client.is_allowed_by_robots(self.source_url):
            return FetchResult(
                provider_id=self.provider_id,
                source_url=self.source_url,
                status_code=999,  # synthetic: blocked by robots
                text="",
                etag=None,
                last_modified=None,
                not_modified=False,
            )
        etag, last_mod = load_etag_cache(self.provider_id)
        status, body, headers = await client.fetch(
            self.source_url, etag=etag, last_modified=last_mod
        )
        not_modified = status == 304
        new_etag = headers.get("etag") or headers.get("ETag")
        new_lm = headers.get("last-modified") or headers.get("Last-Modified")
        save_etag_cache(self.provider_id, new_etag, new_lm)
        raw_path: Path | None = None
        if status == 200 and body:
            raw_path = save_raw(self.provider_id, body)
        return FetchResult(
            provider_id=self.provider_id,
            source_url=self.source_url,
            status_code=status,
            text=body,
            etag=new_etag,
            last_modified=new_lm,
            not_modified=not_modified,
            raw_path=raw_path,
        )


# ============================================================
# Registry
# ============================================================


@dataclass
class CollectorRegistry:
    collectors: list[BaseCollector] = field(default_factory=list)

    def register(self, c: BaseCollector) -> None:
        self.collectors.append(c)

    def all(self) -> list[BaseCollector]:
        return list(self.collectors)

    def by_id(self, provider_id: str) -> BaseCollector | None:
        for c in self.collectors:
            if c.provider_id == provider_id:
                return c
        return None
