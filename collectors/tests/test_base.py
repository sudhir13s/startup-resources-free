from __future__ import annotations

import asyncio
from typing import Any

import httpx

from collectors.base import (
    BaseCollector,
    PoliteClient,
)


class FakeCollector(BaseCollector):
    provider_id = "fake"
    provider_name = "Fake"
    category = "ai-api"
    source_url = "https://example.com/pricing"

    def extract_fields(self, body: str) -> dict[str, Any]:
        return {"id": self.provider_id, "name": self.provider_name, "headline": body[:50]}


def _client_with_handler(
    handler: "callable[[httpx.Request], httpx.Response]",
) -> PoliteClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(transport=transport, follow_redirects=True)
    # Disable inter-request delay for tests.
    return PoliteClient(client=inner, rate_limit_s=0.0)


# ---------- robots.txt ----------


def test_collector_blocks_when_robots_disallows(tmp_path, monkeypatch):
    from collectors import base as base_mod

    monkeypatch.setattr(base_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(base_mod, "RAW_ROOT", tmp_path / "data" / "raw")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nDisallow: /pricing\n"
            )
        if req.url.path == "/pricing":
            return httpx.Response(200, text="<html>quota</html>")
        return httpx.Response(404)

    async def go():
        async with _client_with_handler(handler) as client:
            return await FakeCollector().collect(client)

    result = asyncio.run(go())
    assert result.status_code == 999
    assert result.text == ""
    assert result.raw_path is None


def test_collector_fetches_when_robots_allows(tmp_path, monkeypatch):
    from collectors import base as base_mod

    monkeypatch.setattr(base_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(base_mod, "RAW_ROOT", tmp_path / "data" / "raw")

    body = "<html>14,400 requests per day quota</html>"

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if req.url.path == "/pricing":
            return httpx.Response(
                200,
                text=body,
                headers={"ETag": "abc123", "Last-Modified": "Sat, 26 Apr 2026 00:00:00 GMT"},
            )
        return httpx.Response(404)

    async def go():
        async with _client_with_handler(handler) as client:
            return await FakeCollector().collect(client)

    result = asyncio.run(go())
    assert result.status_code == 200
    assert result.text == body
    assert result.etag == "abc123"
    assert result.raw_path is not None
    assert result.raw_path.exists()


# ---------- ETag caching ----------


def test_second_fetch_sends_if_none_match_header(tmp_path, monkeypatch):
    from collectors import base as base_mod

    monkeypatch.setattr(base_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(base_mod, "RAW_ROOT", tmp_path / "data" / "raw")

    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if req.url.path == "/pricing":
            inm = req.headers.get("if-none-match")
            seen["if_none_match"] = inm or ""
            if inm == "abc123":
                return httpx.Response(304, text="")
            return httpx.Response(200, text="<body>x</body>", headers={"ETag": "abc123"})
        return httpx.Response(404)

    async def go():
        async with _client_with_handler(handler) as client:
            r1 = await FakeCollector().collect(client)
            r2 = await FakeCollector().collect(client)
            return r1, r2

    r1, r2 = asyncio.run(go())
    assert r1.status_code == 200
    assert r2.status_code == 304
    assert r2.not_modified is True
    assert seen["if_none_match"] == "abc123"


# ---------- rate limiting ----------


def test_rate_limit_waits_between_requests():
    import time

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(transport=transport)

    async def go():
        client = PoliteClient(client=inner, rate_limit_s=0.2)
        try:
            t0 = time.monotonic()
            await client.fetch("https://example.com/a")
            await client.fetch("https://example.com/b")
            return time.monotonic() - t0
        finally:
            await client.aclose()

    elapsed = asyncio.run(go())
    # Second request must have waited ~0.2 s after the first.
    assert elapsed >= 0.15


# ---------- User-Agent default ----------


def test_user_agent_is_identifiable():
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["ua"] = req.headers.get("user-agent", "")
        return httpx.Response(200, text="")

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(transport=transport, headers={"User-Agent": PoliteClient().user_agent})

    async def go():
        client = PoliteClient(client=inner, rate_limit_s=0.0)
        try:
            await client.fetch("https://example.com/a")
        finally:
            await client.aclose()

    asyncio.run(go())
    assert "ResourceOS-Scraper" in seen["ua"]
    assert "github.com/sudhir13s" in seen["ua"]
