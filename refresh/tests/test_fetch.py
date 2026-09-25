from __future__ import annotations

import asyncio

import httpx

from refresh.fetch import PoliteFetcher, has_pricing_signal

PRICING_HTML = (
    "<html><body><p>Free tier: 100 requests/day, always free. "
    + ("Plenty of detail about the plan and its limits goes here. " * 10)
    + "</p></body></html>"
)
SHORT_HTML = "<html><body><p>x</p></body></html>"


def _fetcher(repo, handler, *, min_interval_s: float = 0, **kwargs) -> PoliteFetcher:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return PoliteFetcher(repo, min_interval_s=min_interval_s, client=client, **kwargs)


def test_should_skip_when_robots_disallows(repo):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /pricing")
        return httpx.Response(200, text=PRICING_HTML)

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/pricing"))

    assert outcome.robots_blocked is True
    assert outcome.ok is False


def test_should_fetch_when_robots_allows(repo):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=PRICING_HTML)

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/pricing"))

    assert outcome.ok is True
    assert "Free tier" in outcome.text


def test_should_honor_per_host_interval(repo):
    calls: list[float] = []
    import time

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(time.monotonic())
        return httpx.Response(200, text=PRICING_HTML)

    fetcher = _fetcher(repo, handler, min_interval_s=0.05)

    async def two_fetches():
        await fetcher.fetch("https://example.com/a")
        await fetcher.fetch("https://example.com/b")

    start = time.monotonic()
    asyncio.run(two_fetches())
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05


def test_should_fallback_to_jina_when_text_short(repo):
    call_log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if "r.jina.ai" in str(request.url):
            return httpx.Response(200, text="Full readable content from Jina, much longer than the original short page text.")
        return httpx.Response(200, text=SHORT_HTML)

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/app"))

    assert outcome.via_jina is True
    assert "Jina" in outcome.text
    assert any("r.jina.ai" in u for u in call_log)


def test_should_fallback_to_jina_when_status_403(repo):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if "r.jina.ai" in str(request.url):
            return httpx.Response(200, text="Jina rescued content")
        return httpx.Response(403, text="blocked")

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/blocked"))

    assert outcome.via_jina is True
    assert "Jina" in outcome.text


def test_should_store_and_reuse_etag(repo):
    request_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        request_count["n"] += 1
        if request.headers.get("If-None-Match") == "abc123":
            return httpx.Response(304)
        return httpx.Response(200, text=PRICING_HTML, headers={"ETag": "abc123"})

    fetcher = _fetcher(repo, handler)
    first = asyncio.run(fetcher.fetch("https://example.com/pricing"))
    second = asyncio.run(fetcher.fetch("https://example.com/pricing"))

    assert first.status_code == 200
    assert second.not_modified is True


def test_should_retry_on_503_then_succeed(repo):
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts["n"] += 1
        if attempts["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, text=PRICING_HTML)

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/flaky"))

    assert outcome.ok is True
    assert attempts["n"] == 2  # first attempt 503, one retry succeeds
    assert "Free tier" in outcome.text


def test_should_not_retry_on_404(repo):
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts["n"] += 1
        return httpx.Response(404, text="not found")

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch("https://example.com/missing"))

    assert outcome.ok is False
    assert attempts["n"] == 1


def test_should_follow_pricing_link_when_landing_page_lacks_signal(repo):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><body>Welcome. <a href="/pricing">Pricing</a></body></html>',
            )
        if request.url.path == "/pricing":
            return httpx.Response(200, text=PRICING_HTML)
        return httpx.Response(404)

    fetcher = _fetcher(repo, handler)
    outcome = asyncio.run(fetcher.fetch_with_follow("https://example.com/"))

    assert "Free tier" in outcome.text


def test_has_pricing_signal_detects_free_tier_language():
    assert has_pricing_signal("This plan is always free forever") is True
    assert has_pricing_signal("Contact sales for enterprise pricing") is False
