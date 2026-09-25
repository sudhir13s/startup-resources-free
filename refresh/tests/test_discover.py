from __future__ import annotations

import asyncio
import json

import httpx

import freellm
from refresh.discover import (
    build_queries,
    candidate_id,
    discover,
    known_domains,
    registrable_domain,
)
from refresh.fetch import PoliteFetcher
from refresh.search import TavilyProvider, get_chain
from refresh.tests.conftest import ScriptedBackend


def test_should_strip_www_when_computing_registrable_domain():
    assert registrable_domain("https://www.groq.com/pricing") == "groq.com"
    assert registrable_domain("https://console.groq.com/docs") == "console.groq.com"


def test_should_collect_domains_from_source_urls_and_links(groq_record):
    domains = known_domains([groq_record])
    assert "console.groq.com" in domains


def test_should_be_stable_and_ignore_query_string_when_hashing_candidate_id():
    a = candidate_id("https://example.com/offer?utm=1")
    b = candidate_id("https://example.com/offer?utm=2")
    assert a == b


def test_should_include_india_phrasing_for_grant_category():
    queries = build_queries(category="grant")
    assert any("India" in q for q in queries)


def _fetcher(handler, repo) -> PoliteFetcher:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return PoliteFetcher(repo, min_interval_s=0, client=client)


def test_should_dedupe_and_exclude_known_domains_when_discovering(
    repo, monkeypatch, all_llm_keys_present
):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    def search_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if "tavily" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"url": "https://known.com/free", "title": "Known"},
                        {"url": "https://new-provider.com/free", "title": "New"},
                    ]
                },
            )
        return httpx.Response(404)

    fetcher = _fetcher(search_handler, repo)
    chain = get_chain(repo, providers=[TavilyProvider()])
    ranked_response = json.dumps(
        {
            "candidates": [
                {
                    "url": "https://new-provider.com/free",
                    "title": "New Provider",
                    "category_guess": "cloud",
                    "score": 0.8,
                    "reason": "genuine free tier",
                }
            ]
        }
    )
    freellm.set_backend(ScriptedBackend([ranked_response] * 10))

    outcome = asyncio.run(
        discover(
            chain=chain,
            fetcher=fetcher,
            known={"known.com"},
            categories=("cloud",),
            max_per_category=5,
        )
    )

    urls = [c.url for c in outcome.candidates]
    assert "https://new-provider.com/free" in urls
    assert all("known.com" not in u for u in urls)


def test_should_record_error_when_search_chain_exhausted(repo, all_llm_keys_present):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(404)

    fetcher = _fetcher(handler, repo)
    chain = get_chain(repo, providers=[])  # no providers available

    outcome = asyncio.run(
        discover(chain=chain, fetcher=fetcher, known=set(), categories=("cloud",))
    )

    assert outcome.chain_exhausted is True
    assert outcome.errors


def test_should_not_crash_when_ranking_fails(repo, monkeypatch, all_llm_keys_present):
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if "tavily" in str(request.url):
            return httpx.Response(
                200, json={"results": [{"url": "https://x.com/free", "title": "X"}]}
            )
        return httpx.Response(404)

    fetcher = _fetcher(handler, repo)
    chain = get_chain(repo, providers=[TavilyProvider()])
    freellm.set_backend(ScriptedBackend(["not valid json"] * 10))

    outcome = asyncio.run(
        discover(chain=chain, fetcher=fetcher, known=set(), categories=("cloud",))
    )

    assert outcome.candidates == []
    assert any("ranking failed" in e for e in outcome.errors)
