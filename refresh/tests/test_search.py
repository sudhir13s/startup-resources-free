from __future__ import annotations

import asyncio

import httpx
import pytest

from refresh.search import (
    AllSearchProvidersExhaustedError,
    ExaProvider,
    JinaProvider,
    LinkupProvider,
    SerpAPIProvider,
    TavilyProvider,
    chain_status,
    get_chain,
)


def test_should_return_empty_chain_when_no_keys_configured(repo, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("LINKUP_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)

    chain = get_chain(repo)
    assert chain.names() == []
    with pytest.raises(AllSearchProvidersExhaustedError):
        asyncio.run(chain.search("free postgres"))


def test_should_rotate_to_next_provider_on_429(repo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")
    monkeypatch.setenv("EXA_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        if "tavily" in str(request.url):
            return httpx.Response(429, text="rate limited")
        return httpx.Response(
            200,
            json={"results": [{"url": "https://example.com/free-tier", "title": "Free", "text": "..."}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[TavilyProvider(), ExaProvider()])

    results = asyncio.run(chain.search("free tier", client=client))
    assert len(results) == 1
    assert results[0].source_provider == "exa"


def test_should_persist_quota_across_chain_instances(repo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"url": "https://example.com/x", "title": "X"}]})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    chain1 = get_chain(repo, providers=[TavilyProvider()])
    asyncio.run(chain1.search("q1", client=client))

    chain2 = get_chain(repo, providers=[TavilyProvider()])
    assert chain2.quotas.get("tavily", 1000).requests_used == 1


def test_should_raise_when_all_providers_exhausted(repo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[TavilyProvider()])

    with pytest.raises(AllSearchProvidersExhaustedError):
        asyncio.run(chain.search("q", client=client))


def test_should_treat_empty_results_as_success_not_fallthrough(repo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")
    monkeypatch.setenv("EXA_API_KEY", "fake")
    exa_called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "tavily" in str(request.url):
            return httpx.Response(200, json={"results": []})
        exa_called["n"] += 1
        return httpx.Response(200, json={"results": [{"url": "https://x.com", "title": "X"}]})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[TavilyProvider(), ExaProvider()])

    results = asyncio.run(chain.search("q", client=client))
    assert results == []
    assert exa_called["n"] == 0


def test_should_parse_jina_search_results(repo, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"url": "https://jina-result.com", "title": "Jina Hit", "description": "desc"}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[JinaProvider()])

    results = asyncio.run(chain.search("free tier", client=client))
    assert results[0].url == "https://jina-result.com"
    assert results[0].source_provider == "jina"


def test_should_parse_linkup_search_results(repo, monkeypatch):
    monkeypatch.setenv("LINKUP_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"results": [{"url": "https://linkup-result.com", "name": "Linkup Hit"}]}
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[LinkupProvider()])

    results = asyncio.run(chain.search("free tier", client=client))
    assert results[0].url == "https://linkup-result.com"
    assert results[0].title == "Linkup Hit"


def test_should_parse_serpapi_search_results(repo, monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"organic_results": [{"link": "https://serp-result.com", "title": "Serp Hit"}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    chain = get_chain(repo, providers=[SerpAPIProvider()])

    results = asyncio.run(chain.search("free tier", client=client))
    assert results[0].url == "https://serp-result.com"


def test_chain_status_reports_active_providers_and_remaining(repo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("LINKUP_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)

    status = chain_status(repo)
    assert status["providers_active"] == ["tavily"]
