"""Shared fixtures for refresh tests.

Real SqliteRepository in tmp_path (never mocked, per test-patterns.md).
Web calls go through httpx.MockTransport. LLM calls go through a scripted
`ScriptedBackend` set via `freellm.set_backend` — the external boundary is
the only thing mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from domain.records import ProviderRecord
from freellm import PROVIDERS, set_backend
from freellm.schemas import Result
from storage.sqlite_repository import SqliteRepository

FIXTURE = Path(__file__).resolve().parent.parent.parent / "domain" / "fixtures" / "sample_records.json"


@pytest.fixture
def repo(tmp_path):
    instance = SqliteRepository(tmp_path / "resourceos.db")
    yield instance
    instance.close()


@pytest.fixture(autouse=True)
def _isolated_freellm_quotas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every refresh test gets a fresh freellm quota dir and clears the
    backend singleton afterward so tests never leak state to each other."""
    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path / "freellm-quotas"))
    yield
    set_backend(None)


@pytest.fixture
def all_llm_keys_present(monkeypatch: pytest.MonkeyPatch):
    """Set every freellm catalog env var so the LLM chain isn't filtered out."""
    for entries in PROVIDERS.values():
        for e in entries:
            monkeypatch.setenv(e.env_var, "fake-key-not-used")


@pytest.fixture
def sample_records() -> list[ProviderRecord]:
    return [ProviderRecord.model_validate(row) for row in json.loads(FIXTURE.read_text())]


@pytest.fixture
def groq_record(sample_records: list[ProviderRecord]) -> ProviderRecord:
    return next(r for r in sample_records if r.provider_id == "groq")


class ScriptedBackend:
    """Deterministic Backend for extraction tests.

    `text_responses` is a queue of either a JSON-string content, or a
    callable `(messages) -> str`, or an exception instance to raise.
    Each `call_text_one` invocation pops the next entry.
    """

    name = "scripted"

    def __init__(self, text_responses: list[Any] | None = None) -> None:
        self._queue: list[Any] = list(text_responses or [])
        self.calls: list[list[dict]] = []

    def push(self, response: Any) -> None:
        self._queue.append(response)

    async def call_text_one(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        timeout_s: int = 60,
        api_key: str = "",
        base_url: str = "",
        response_format: dict[str, str] | None = None,
    ) -> Result:
        self.calls.append(messages)
        if not self._queue:
            raise RuntimeError("ScriptedBackend queue exhausted")
        item = self._queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        content = item(messages) if isinstance(item, Callable) else item
        return Result(
            content=content, provider_used=provider, model_used=model, latency_ms=1
        )

    async def call_vision_one(self, **kwargs: Any) -> Result:  # pragma: no cover - unused
        raise NotImplementedError

    async def call_embed_one(self, **kwargs: Any) -> Result:  # pragma: no cover - unused
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


def extracted_json(**overrides: Any) -> str:
    """A minimal, valid ProviderRecord JSON payload for scripted LLM replies."""
    base = {
        "provider_id": "groq",
        "name": "Groq",
        "vendor": "Groq",
        "category": "ai-api",
        "source_urls": ["https://console.groq.com/docs/rate-limits"],
        "offer_type": "free-quota",
        "headline": "Fast open-model inference with a daily free quota",
        "highlights": [],
        "services": [
            {
                "name": "Llama 3.3 70B Versatile",
                "category": "ai-api",
                "pricing_layer": "quota",
                "summary": "Chat completions within free rate limits",
                "limits": [{"label": "Requests", "value": 1000, "unit": "requests", "period": "day"}],
            }
        ],
        "credits": [],
        "quota_summary": "Rate-limited free quota",
        "duration_summary": "Always free",
        "region_summary": "Global",
        "eligibility_summary": "Any developer",
        "access_method": "api-key",
        "claim_steps": [],
        "restrictions": [],
        "gotchas": [],
        "links": [],
        "geo_priority": "global-other",
        "use_case_tiers": ["hobby", "personal"],
        "parse_confidence": "high",
        "status": "active",
    }
    base.update(overrides)
    return json.dumps(base)
