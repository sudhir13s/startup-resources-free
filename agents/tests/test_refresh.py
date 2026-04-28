"""Refresh agent — direct-fetch + page-follow re-extraction."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from agents import refresh
from agents.refresh import has_pricing_signal


# ---------- pricing-signal heuristic ----------


def test_has_pricing_signal_matches_obvious():
    assert has_pricing_signal("100 GB free per month")
    assert has_pricing_signal("Free tier — always free")
    assert has_pricing_signal("$0 / month")
    assert has_pricing_signal("750 hrs free")
    assert has_pricing_signal("14400 requests/day")


def test_has_pricing_signal_skips_marketing_fluff():
    assert not has_pricing_signal("Welcome to our company. We help startups.")
    assert not has_pricing_signal("")


# ---------- fetch_with_follows ----------


@pytest.fixture(autouse=True)
def _polite_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Skip robots + drop the 30 s rate-limit so tests stay fast."""

    async def _async_true(self, url):
        return True

    async def _async_noop(self, *a, **kw):
        return None

    monkeypatch.setattr(
        "collectors.base.PoliteClient.is_allowed_by_robots",
        _async_true,
        raising=True,
    )
    monkeypatch.setattr(
        "collectors.base.PoliteClient._wait_for_rate_limit",
        _async_noop,
        raising=True,
    )
    yield


def _async_get_factory(responses):
    """Builds a fake httpx.AsyncClient.get that maps URL prefix -> Response."""

    async def _fake_get(self, url, **kwargs):
        for prefix, payload in responses.items():
            if url.startswith(prefix):
                return httpx.Response(
                    status_code=payload.get("status", 200),
                    content=payload.get("body", "").encode("utf-8"),
                    headers={"content-type": "text/html"},
                    request=httpx.Request("GET", url),
                )
        return httpx.Response(404, request=httpx.Request("GET", url))

    return _fake_get


def test_fetch_with_follows_returns_landing_when_signal_present(
    monkeypatch: pytest.MonkeyPatch,
):
    responses = {
        "https://x.test": {"body": "Free tier — always free, 100 GB/mo"},
    }
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    from collectors.base import PoliteClient

    async def go():
        async with PoliteClient(rate_limit_s=0.0) as client:
            return await refresh.fetch_with_follows(
                client, source_url="https://x.test/"
            )

    text, pages = asyncio.run(go())
    assert "Free tier" in text
    assert pages == ["https://x.test/"]  # only landing visited


def test_fetch_with_follows_walks_to_pricing(monkeypatch: pytest.MonkeyPatch):
    """Landing page has no pricing signal -> follow to /pricing."""
    responses = {
        "https://y.test/pricing": {
            "body": "Free plan: 5 GB storage, 100 requests/day"
        },
        "https://y.test": {"body": "Welcome to Y. We do things."},
    }
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    from collectors.base import PoliteClient

    async def go():
        async with PoliteClient(rate_limit_s=0.0) as client:
            return await refresh.fetch_with_follows(
                client, source_url="https://y.test/", max_follows=2
            )

    text, pages = asyncio.run(go())
    assert "5 GB storage" in text
    assert any("/pricing" in p for p in pages)


def test_fetch_with_follows_caps_at_max(monkeypatch: pytest.MonkeyPatch):
    """If no follow has signal, we should stop after max_follows."""
    responses = {
        "https://z.test": {"body": "marketing"},
    }  # all paths return same fluff
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    from collectors.base import PoliteClient

    async def go():
        async with PoliteClient(rate_limit_s=0.0) as client:
            return await refresh.fetch_with_follows(
                client, source_url="https://z.test/", max_follows=2
            )

    _, pages = asyncio.run(go())
    # Landing + at most 2 follows = 3 pages total
    assert len(pages) <= 3


# ---------- refresh_all (end-to-end with scripted backend) ----------


def test_refresh_all_skips_unchanged_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scripted_backend
):
    """Set up DB with a record. Mock fetch + extractor to return SAME data.
    refresh_all should mark unchanged + write 0 new rows."""
    db_path = tmp_path / "x.db"
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(db_path))

    from backend import db as db_module
    from schema.records import ProviderRecord

    record = ProviderRecord(
        id="seed:render",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.test/pricing",
        offer_type="free-tier",
        offer_summary="Free Web Services with 750 hrs/month.",
        quota_summary="750 hrs / mo",
        duration_summary="Always free (sleeps)",
        region_summary="US / EU / SG",
        eligibility_summary="Any user",
        india_accessible=True,
        geo_priority="global-other",
        scraped_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 26),
    )
    with db_module.db_session(db_path) as conn:
        db_module.apply_migrations(conn)
        db_module.insert_record(conn, record)

    # Fetch returns a page with pricing signal so we don't follow
    responses = {
        "https://render.test": {
            "body": "Free tier — 750 hrs/mo of free Web Service compute."
        }
    }
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    # Scripted extractor returns the SAME shape -> change_detector says unchanged
    scripted_backend.script(
        "extractor",
        json.dumps(
            {
                "provider_id": "render",
                "provider_name": "Render",
                "category": "cloud",
                "headline": record.headline,
                "offer_summary": record.offer_summary,
                "offer_type": "free-tier",
                "quota_summary": record.quota_summary,
                "duration_summary": record.duration_summary,
                "region_summary": record.region_summary,
                "eligibility_summary": record.eligibility_summary,
                "geo_priority": "global-other",
                "india_accessible": True,
            }
        ),
    )

    summary = asyncio.run(
        refresh.refresh_all(
            db_path=db_path, backend=scripted_backend, rate_limit_s=0.0
        )
    )
    assert summary.walked == 1
    assert summary.unchanged == 1
    assert summary.changed == 0


def test_refresh_all_records_change_when_extractor_returns_different(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scripted_backend
):
    db_path = tmp_path / "y.db"
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(db_path))

    from backend import db as db_module
    from schema.records import ProviderRecord

    record = ProviderRecord(
        id="seed:vercel",
        provider_id="vercel",
        provider_name="Vercel",
        category="cloud",
        source_url="https://vercel.test/pricing",
        offer_type="free-tier",
        offer_summary="100 GB bandwidth.",
        quota_summary="100 GB / mo",
        duration_summary="Always free",
        region_summary="Global",
        eligibility_summary="Any user",
        india_accessible=True,
        geo_priority="global-other",
        scraped_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 26),
    )
    with db_module.db_session(db_path) as conn:
        db_module.apply_migrations(conn)
        db_module.insert_record(conn, record)

    responses = {
        "https://vercel.test": {
            "body": "Free tier reduced to 50 GB bandwidth this month."
        }
    }
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    scripted_backend.script(
        "extractor",
        json.dumps(
            {
                "provider_id": "vercel",
                "provider_name": "Vercel",
                "category": "cloud",
                "offer_summary": "Reduced to 50 GB bandwidth — down from 100 GB.",
                "offer_type": "free-tier",
                "quota_summary": "50 GB / mo",
                "duration_summary": "Always free",
                "region_summary": "Global",
                "eligibility_summary": "Any user",
                "geo_priority": "global-other",
                "india_accessible": True,
            }
        ),
    )

    summary = asyncio.run(
        refresh.refresh_all(
            db_path=db_path, backend=scripted_backend, rate_limit_s=0.0
        )
    )
    assert summary.walked == 1
    assert summary.changed == 1
    assert summary.inserted_change_reports == 1


def test_refresh_all_handles_extract_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scripted_backend
):
    db_path = tmp_path / "z.db"
    monkeypatch.setenv("RESOURCEOS_DB_PATH", str(db_path))

    from backend import db as db_module
    from schema.records import ProviderRecord

    record = ProviderRecord(
        id="seed:render",
        provider_id="render",
        provider_name="Render",
        category="cloud",
        source_url="https://render.test/",
        offer_type="free-tier",
        offer_summary="x",
        quota_summary="x",
        duration_summary="x",
        region_summary="x",
        eligibility_summary="x",
        india_accessible=True,
        geo_priority="global-other",
        scraped_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        parse_confidence="high",
        source_method="manual",
        last_verified_at=date(2026, 4, 26),
    )
    with db_module.db_session(db_path) as conn:
        db_module.apply_migrations(conn)
        db_module.insert_record(conn, record)

    responses = {"https://render.test": {"body": "Free tier"}}
    monkeypatch.setattr("httpx.AsyncClient.get", _async_get_factory(responses))

    # Garbage from LLM -> extractor returns None
    scripted_backend.script("extractor", "not actually json {")

    summary = asyncio.run(
        refresh.refresh_all(
            db_path=db_path, backend=scripted_backend, rate_limit_s=0.0
        )
    )
    assert summary.walked == 1
    assert summary.extract_failed == 1
    assert summary.changed == 0


# ---------- write_summary ----------


def test_write_summary_persists_dated_file(tmp_path: Path):
    summary = refresh.RefreshSummary(started_at="2026-04-28T00:00:00Z")
    summary.walked = 5
    summary.changed = 2
    out = refresh.write_summary(summary, out_dir=str(tmp_path))
    assert Path(out).exists()
    payload = json.loads(Path(out).read_text(encoding="utf-8"))
    assert payload["walked"] == 5
    assert payload["changed"] == 2
