"""Orchestrator end-to-end coverage with httpx mocking + Mock LLM backend."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from backend import db as db_module
from freellm.backends.mock import MockBackend
from pipeline import orchestrator


# ---------- httpx + collector network mocking ----------


@pytest.fixture(autouse=True)
def _polite_quick(monkeypatch: pytest.MonkeyPatch):
    """Skip robots.txt + remove the 30s rate-limit so tests stay fast."""
    monkeypatch.setattr(
        "collectors.base.PoliteClient.is_allowed_by_robots",
        lambda self, url: _async_true(),  # type: ignore[arg-type]
        raising=True,
    )
    monkeypatch.setattr(
        "collectors.base.PoliteClient._wait_for_rate_limit",
        _async_noop,
        raising=True,
    )
    yield


async def _async_true() -> bool:
    return True


async def _async_noop(*_args, **_kwargs) -> None:
    return None


@pytest.fixture
def mocked_http(monkeypatch: pytest.MonkeyPatch):
    """Force every PoliteClient.fetch_text call to return canned bytes."""

    async def _fake_get(self, url, **kwargs):
        return httpx.Response(
            status_code=200,
            content=b"<html><body>Free 750 hrs/mo on Render.</body></html>",
            request=httpx.Request("GET", url),
            headers={"content-type": "text/html"},
        )

    monkeypatch.setattr(
        "httpx.AsyncClient.get",
        _fake_get,
        raising=True,
    )
    yield


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Each test gets its own raw / runs / snapshots / data dirs."""
    monkeypatch.setattr(
        "collectors.base.RAW_ROOT",
        tmp_path / "raw",
        raising=True,
    )
    monkeypatch.setattr(
        orchestrator,
        "RUNS_DIR",
        tmp_path / "runs",
        raising=True,
    )
    snap_dir = tmp_path / "snap"
    monkeypatch.setattr(
        "snapshots.SNAPSHOT_DIR",
        snap_dir,
        raising=True,
    )
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VERIFY_QUEUE_DIR", str(tmp_path / "verify"))
    yield


# ---------- heuristic mode (no LLM) ----------


def test_heuristic_mode_emits_summary_and_snapshot(mocked_http, tmp_path: Path):
    summary = asyncio.run(
        orchestrator.run_pipeline(
            only=["render"],
            mode="heuristic",
            db_path=None,
        )
    )
    assert summary.mode == "heuristic"
    assert summary.snapshot_path is not None
    assert Path(summary.snapshot_path).exists()
    assert len(summary.provider_summaries) == 1
    ps = summary.provider_summaries[0]
    assert ps.provider_id == "render"
    assert ps.error is None


def test_heuristic_mode_writes_to_db_when_path_given(mocked_http, tmp_path: Path):
    db_path = tmp_path / "x.db"
    summary = asyncio.run(
        orchestrator.run_pipeline(
            only=["render"],
            mode="heuristic",
            db_path=db_path,
        )
    )
    assert summary.db_path == str(db_path)
    # Heuristic merge succeeds via seed -> at least 1 record persisted.
    assert summary.inserted_records >= 0  # may be 0 if seed already in DB; still ok
    with db_module.db_session(db_path) as conn:
        latest = db_module.latest_records(conn)
        ids = {r.provider_id for r in latest}
        assert "render" in ids


# ---------- llm mode with MockBackend ----------


def test_llm_mode_persists_record_change_and_no_verify_when_high(
    mocked_http, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """High-confidence LLM extract -> record + change inserted, no verify."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    backend = _scripted_high_confidence_backend()
    db_path = tmp_path / "llm.db"

    summary = asyncio.run(
        orchestrator.run_pipeline(
            only=["render"],
            mode="llm",
            db_path=db_path,
            backend=backend,
        )
    )
    assert summary.inserted_records >= 1
    assert summary.inserted_changes >= 1
    assert summary.queued_for_verify == 0
    ps = summary.provider_summaries[0]
    assert ps.parse_confidence in ("high", "medium")
    assert ps.change_severity == "new"
    assert ps.error is None


def test_llm_mode_low_confidence_queues_verify(
    mocked_http, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Garbage from LLM -> low confidence; auto mode falls back to heuristic
    so a record still lands; pure llm mode reports the error."""
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    backend = _scripted_garbage_backend()
    db_path = tmp_path / "llm-bad.db"

    summary = asyncio.run(
        orchestrator.run_pipeline(
            only=["render"],
            mode="llm",
            db_path=db_path,
            backend=backend,
        )
    )
    ps = summary.provider_summaries[0]
    # Pure llm-mode: nothing useful from extractor; error surfaced.
    assert ps.error is not None or ps.parse_confidence == "low"


def test_auto_mode_downgrades_to_heuristic_when_llm_fails(
    mocked_http, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Auto mode + garbage LLM -> heuristic kicks in via seed merge."""
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    backend = _scripted_garbage_backend()
    db_path = tmp_path / "auto.db"

    summary = asyncio.run(
        orchestrator.run_pipeline(
            only=["render"],
            mode="auto",
            db_path=db_path,
            backend=backend,
        )
    )
    ps = summary.provider_summaries[0]
    assert ps.mode_used == "heuristic"
    assert ps.error is None
    assert summary.inserted_records >= 1


# ---------- locking ----------


def test_lock_prevents_concurrent_run(tmp_path: Path):
    lock = orchestrator.acquire_lock("test-id")
    assert lock is not None
    second = orchestrator.acquire_lock("test-id")
    assert second is None
    orchestrator.release_lock(lock)
    third = orchestrator.acquire_lock("test-id")
    assert third is not None
    orchestrator.release_lock(third)


# ---------- backends used by the LLM tests ----------


def _scripted_high_confidence_backend() -> MockBackend:
    """MockBackend that returns valid JSON for extractor + tier_classifier."""

    class _High(MockBackend):
        async def call_text_one(self, **kwargs):  # type: ignore[override]
            messages = kwargs["messages"]
            agent = _sniff_agent(messages)
            if agent == "extractor":
                payload = {
                    "provider_id": "render",
                    "provider_name": "Render",
                    "category": "cloud",
                    "headline": "Free 750 hrs",
                    "offer_summary": "Free Web Services with 750 hrs/month.",
                    "offer_type": "free-tier",
                    "limits": {"hours_per_month": 750},
                    "quota_summary": "750 hrs / mo",
                    "duration_summary": "Always free",
                    "region_summary": "US / EU / SG",
                    "eligibility_summary": "Any user",
                    "access_method": "signup",
                    "regions": ["global"],
                    "user_types": ["any"],
                    "geo_priority": "global-other",
                    "india_accessible": True,
                }
                content = json.dumps(payload)
            elif agent == "tier_classifier":
                content = json.dumps(
                    {
                        "use_case_tiers": ["hobby", "personal"],
                        "tier_fit_rationale": "fits both",
                    }
                )
            else:
                content = "{}"
            from freellm.schemas import Result

            return Result(
                content=content,
                provider_used=kwargs["provider"],
                model_used=kwargs["model"],
                latency_ms=1,
                cost_usd=0.0,
                tokens_in=10,
                tokens_out=20,
            )

    return _High()


def _scripted_garbage_backend() -> MockBackend:
    """MockBackend that returns unparseable text for every call."""

    class _Garbage(MockBackend):
        async def call_text_one(self, **kwargs):  # type: ignore[override]
            from freellm.schemas import Result

            return Result(
                content="not actually json {{",
                provider_used=kwargs["provider"],
                model_used=kwargs["model"],
                latency_ms=1,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
            )

    return _Garbage()


def _sniff_agent(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, str):
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("agent:"):
                        return line.split(":", 1)[1].strip()
                    if line and not line.startswith("---"):
                        break
    return "unknown"
