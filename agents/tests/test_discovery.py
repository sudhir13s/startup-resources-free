"""Discovery agent — exclusion-aware NEW provider hunt + LLM ranking."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx

from agents import discovery


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCH_QUOTA_DIR", str(tmp_path))
    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path))
    yield


@pytest.fixture(autouse=True)
def _clear_search_keys(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "JINA_API_KEY",
        "LINKUP_API_KEY",
        "SERPAPI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------- build_queries ----------


def test_build_queries_includes_site_exclusions():
    queries = discovery.build_queries(
        category="cloud",
        excludes={"render.com", "vercel.com"},
    )
    for q in queries:
        assert "-site:render.com" in q
        assert "-site:vercel.com" in q


def test_build_queries_caps_excludes_to_avoid_query_too_long():
    huge = {f"provider-{i}.com" for i in range(200)}
    queries = discovery.build_queries(
        category="ai-api",
        excludes=huge,
        max_excludes_per_query=10,
    )
    for q in queries:
        # Count `-site:` occurrences should match the cap, not the full set.
        assert q.count("-site:") == 10


def test_build_queries_falls_back_for_unknown_category():
    queries = discovery.build_queries(category="unknown-cat", excludes=set())
    assert len(queries) >= 1
    assert "unknown-cat" in queries[0]


# ---------- collect_known_domains ----------


def test_collect_known_domains_unions_seed_and_yaml(tmp_path: Path, monkeypatch):
    fake_seed = tmp_path / "seed.json"
    fake_seed.write_text(
        json.dumps([{"id": "a", "source_url": "https://A-SEED.test/x"}]),
        encoding="utf-8",
    )
    domains = discovery.collect_known_domains(seed_path=str(fake_seed))
    assert "a-seed.test" in domains  # lowercased


# ---------- collect_from_aggregators ----------


@respx.mock
def test_collect_from_aggregators_dedupes_known(monkeypatch: pytest.MonkeyPatch):
    """Aggregator returns 3 links; one is already-known and gets filtered."""
    from agents import aggregators as agg_mod

    fake_source = agg_mod.AggregatorSource(
        url="https://aggregator.test/",
        category_hint="grant",
    )
    # Patch AGGREGATORS to just our fixture
    monkeypatch.setattr(agg_mod, "AGGREGATORS", (fake_source,))

    respx.get("https://aggregator.test/").mock(
        return_value=httpx.Response(
            200,
            text="""
            <a href="https://known.test/page">known</a>
            <a href="https://new1.test/">new1</a>
            <a href="https://new2.test/">new2</a>
            """,
        )
    )
    cands, fetched = asyncio.run(
        discovery.collect_from_aggregators(known_domains={"known.test"})
    )
    assert fetched == 1
    domains = {c.domain() for c in cands}
    assert "new1.test" in domains
    assert "new2.test" in domains
    assert "known.test" not in domains


@respx.mock
def test_collect_from_aggregators_handles_fetch_error_gracefully(
    monkeypatch: pytest.MonkeyPatch,
):
    from agents import aggregators as agg_mod

    fake = agg_mod.AggregatorSource(url="https://broken.test/", category_hint="cloud")
    monkeypatch.setattr(agg_mod, "AGGREGATORS", (fake,))
    respx.get("https://broken.test/").mock(return_value=httpx.Response(500))
    cands, fetched = asyncio.run(
        discovery.collect_from_aggregators(known_domains=set())
    )
    assert fetched == 0
    assert cands == []


# ---------- collect_from_search ----------


@respx.mock
def test_collect_from_search_dedupes_against_known(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://known.test/x", "title": "K"},
                    {"url": "https://fresh-A.test/", "title": "Fresh A"},
                    {"url": "https://fresh-A.test/other", "title": "Fresh A dup"},
                ]
            },
        )
    )
    cands, qrun = asyncio.run(
        discovery.collect_from_search(
            category="cloud", known_domains={"known.test"}
        )
    )
    domains = {c.domain() for c in cands}
    assert "fresh-a.test" in domains
    assert "known.test" not in domains
    # Same-domain dup within the run is dropped (case-insensitive on domain).
    assert sum(1 for c in cands if c.domain() == "fresh-a.test") == 1
    assert qrun >= 1


@respx.mock
def test_collect_from_search_handles_chain_exhausted(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(429)
    )
    cands, qrun = asyncio.run(
        discovery.collect_from_search(category="cloud", known_domains=set())
    )
    # No results, no exception — caller decides how to flag.
    assert cands == []


# ---------- rank_candidates ----------


def test_rank_candidates_falls_back_on_garbage_llm(scripted_backend):
    from freellm.backends.mock import MockBackend
    from freellm.schemas import Result

    class Garbage(MockBackend):
        async def call_text_one(self, **kwargs):
            return Result(
                content="not actually json {",
                provider_used=kwargs["provider"],
                model_used=kwargs["model"],
                latency_ms=1,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
            )

    cands = [
        discovery.CandidateURL(
            url=f"https://x{i}.test/",
            title=f"X{i}",
            category="cloud",
            score=1.0 - i * 0.1,
            rationale="",
            discovered_via="search:tavily",
        )
        for i in range(3)
    ]
    out = asyncio.run(
        discovery.rank_candidates(cands, category="cloud", backend=Garbage())
    )
    # Garbage LLM -> falls back to native score sort, top 3.
    assert len(out) == 3
    assert out[0].url == "https://x0.test/"


def test_rank_candidates_uses_llm_scoring_when_valid(scripted_backend):
    scripted_backend.script(
        "discovery",
        json.dumps(
            {
                "candidates": [
                    {
                        "url": "https://x0.test/",
                        "title": "Better",
                        "category": "cloud",
                        "score": 0.9,
                        "rationale": "looks legit",
                    }
                ]
            }
        ),
    )
    cands = [
        discovery.CandidateURL(
            url="https://x0.test/",
            title="Original",
            category="cloud",
            score=0.5,
            rationale="",
            discovered_via="search:tavily",
        )
    ]
    out = asyncio.run(
        discovery.rank_candidates(cands, category="cloud", backend=scripted_backend)
    )
    assert len(out) == 1
    assert out[0].title == "Better"
    assert out[0].score == 0.9
    assert out[0].rationale == "looks legit"


# ---------- write_summary ----------


def test_write_summary_persists_to_dated_file(tmp_path: Path):
    summary = discovery.DiscoverySummary(started_at="2026-04-28T00:00:00Z")
    summary.candidates.append(
        discovery.CandidateURL(
            url="https://x.test/",
            title="X",
            category="cloud",
            score=0.8,
            rationale="r",
            discovered_via="search:tavily",
        )
    )
    out = discovery.write_summary(summary, out_dir=str(tmp_path))
    assert Path(out).exists()
    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    assert payload["totals"]["candidates"] == 1
    assert payload["candidates"][0]["url"] == "https://x.test/"
