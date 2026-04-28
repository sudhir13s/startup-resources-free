"""Search-chain executor — quota-aware fallback across 5 providers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from agents import search, search_quotas


@pytest.fixture(autouse=True)
def _isolate_quota_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCH_QUOTA_DIR", str(tmp_path))
    yield


@pytest.fixture(autouse=True)
def _clear_keys(monkeypatch: pytest.MonkeyPatch):
    """Default: no provider keys. Tests opt-in to specific providers."""
    for key in (
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "JINA_API_KEY",
        "LINKUP_API_KEY",
        "SERPAPI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------- get_chain ----------


def test_get_chain_with_no_keys_returns_empty():
    chain = search.get_chain()
    assert chain.providers == []


def test_get_chain_picks_up_present_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("JINA_API_KEY", "test-jina")
    chain = search.get_chain()
    assert chain.names() == ["tavily", "jina"]


def test_chain_status_shape():
    s = search.chain_status()
    assert "providers_active" in s
    assert "remaining" in s


# ---------- empty chain raises ----------


def test_empty_chain_raises_immediately():
    chain = search.get_chain()
    with pytest.raises(search.AllSearchProvidersExhaustedError) as exc_info:
        asyncio.run(chain.search("anything"))
    assert exc_info.value.attempted == []


# ---------- happy path: tavily ----------


@respx.mock
def test_tavily_happy_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://a.test/", "title": "A", "content": "snippet a", "score": 0.9},
                    {"url": "https://b.test/", "title": "B", "content": "snippet b"},
                ]
            },
        )
    )
    chain = search.get_chain()
    results = asyncio.run(chain.search("free hosting"))
    assert len(results) == 2
    assert results[0].url == "https://a.test/"
    assert results[0].source_provider == "tavily"
    assert results[0].score == 0.9


# ---------- fall-through on rate-limit ----------


@respx.mock
def test_429_on_tavily_falls_through_to_exa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("EXA_API_KEY", "test-exa")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(429, json={"error": "rate limit"})
    )
    respx.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"url": "https://exa-result.test/", "title": "E"}]},
        )
    )
    chain = search.get_chain()
    results = asyncio.run(chain.search("free hosting"))
    assert len(results) == 1
    assert results[0].source_provider == "exa"

    # Tavily should be marked exhausted for the rest of the month
    state = search_quotas.load()
    tavily_q = state.get("tavily", 1000)
    assert tavily_q.is_exhausted()


# ---------- fall-through on auth error ----------


@respx.mock
def test_403_on_tavily_falls_through(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "bad-key")
    monkeypatch.setenv("JINA_API_KEY", "test-jina")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(403, json={"error": "auth"})
    )
    respx.get(host="s.jina.ai").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"url": "https://j.test/", "title": "J", "description": "x"}]},
        )
    )
    chain = search.get_chain()
    results = asyncio.run(chain.search("anything"))
    assert results[0].source_provider == "jina"


# ---------- all exhausted ----------


@respx.mock
def test_all_exhausted_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.setenv("EXA_API_KEY", "x")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(429)
    )
    respx.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(429)
    )
    chain = search.get_chain()
    with pytest.raises(search.AllSearchProvidersExhaustedError) as exc_info:
        asyncio.run(chain.search("anything"))
    assert "tavily" in exc_info.value.attempted
    assert "exa" in exc_info.value.attempted


# ---------- quota persistence ----------


@respx.mock
def test_quota_persists_across_calls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    asyncio.run(search.get_chain().search("first call"))
    asyncio.run(search.get_chain().search("second call"))
    state = search_quotas.load()
    q = state.get("tavily", 1000)
    assert q.requests_used == 2


# ---------- quota state honored ----------


@respx.mock
def test_pre_exhausted_provider_is_skipped(monkeypatch: pytest.MonkeyPatch):
    """If quota state says tavily is full, don't try it; go straight to exa."""
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.setenv("EXA_API_KEY", "x")
    # Pre-write quota state showing tavily exhausted
    state = search_quotas.SearchQuotas()
    state.entries["tavily"] = search_quotas.ProviderQuota(
        name="tavily",
        month_key=search_quotas._current_month_key(),
        monthly_cap=1000,
        requests_used=1000,
    )
    search_quotas.save(state)

    tavily_route = respx.post("https://api.tavily.com/search")
    respx.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"url": "https://exa.test/", "title": "E"}]}
        )
    )

    results = asyncio.run(search.get_chain().search("anything"))
    assert results[0].source_provider == "exa"
    # Tavily was never called
    assert not tavily_route.called


# ---------- jina + linkup + serpapi providers parse correctly ----------


@respx.mock
def test_jina_provider_parses_data_array(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JINA_API_KEY", "x")
    respx.get(host="s.jina.ai").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"url": "https://x.test/", "title": "X", "description": "d"},
                    {"url": "https://y.test/", "title": "Y", "content": "c"},
                ]
            },
        )
    )
    results = asyncio.run(search.get_chain().search("q"))
    assert len(results) == 2
    assert results[1].snippet  # content fallback


@respx.mock
def test_serpapi_organic_results_parse(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    respx.get("https://serpapi.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "link": "https://serp1.test/",
                        "title": "S1",
                        "snippet": "desc",
                    }
                ]
            },
        )
    )
    results = asyncio.run(search.get_chain().search("q"))
    assert results[0].url == "https://serp1.test/"
    assert results[0].source_provider == "serpapi"


@respx.mock
def test_linkup_provider_parses(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LINKUP_API_KEY", "x")
    respx.post("https://api.linkup.so/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://l.test/", "name": "L", "content": "c"}
                ]
            },
        )
    )
    results = asyncio.run(search.get_chain().search("q"))
    assert results[0].source_provider == "linkup"


# ---------- search-quotas module ----------


def test_quota_month_rollover():
    state = search_quotas.SearchQuotas()
    state.entries["tavily"] = search_quotas.ProviderQuota(
        name="tavily", month_key="2025-01", monthly_cap=1000, requests_used=999
    )
    # Asking for the current month should reset (different key).
    q = state.get("tavily", 1000)
    assert q.month_key == search_quotas._current_month_key()
    assert q.requests_used == 0


def test_quota_unlimited_provider_never_exhausts():
    state = search_quotas.SearchQuotas()
    q = state.get("jina", 0)
    q.requests_used = 1_000_000
    assert not q.is_exhausted()
    assert q.remaining() >= 999_000


def test_quota_record_failure_increments():
    state = search_quotas.SearchQuotas()
    state.record_failure("tavily", 1000, "HTTP 500")
    q = state.get("tavily", 1000)
    assert q.requests_used == 1
    assert q.consecutive_failures == 1
    assert "500" in q.last_failure_reason
