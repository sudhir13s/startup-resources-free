"""Router chain logic — exercised against MockBackend (no network)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from freellm import (
    AllProvidersExhaustedError,
    PROVIDERS,
    call_embed,
    call_text,
    call_vision,
    quotas,
    set_backend,
)
from freellm.backends.mock import MockBackend


@pytest.fixture(autouse=True)
def _isolated_quotas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every test gets a fresh quotas dir + a fresh MockBackend singleton."""
    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path))
    set_backend(MockBackend())
    yield
    set_backend(None)


@pytest.fixture
def _all_keys_present(monkeypatch: pytest.MonkeyPatch):
    """Set every catalog env var so the chain isn't filtered by env."""
    for entries in PROVIDERS.values():
        for e in entries:
            monkeypatch.setenv(e.env_var, "fake-key-not-used")


# ---------- happy path ----------


def test_call_text_picks_first_eligible_provider(_all_keys_present):
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hello"}],
            task_name="text-happy",
        )
    )
    # First text entry in catalog is groq/llama-3.3-70b-versatile.
    assert result.provider_used == "groq"
    assert result.model_used == "llama-3.3-70b-versatile"
    assert "hello" in result.content
    assert result.chain_attempted == ["groq/llama-3.3-70b-versatile"]


def test_call_vision_uses_vision_chain(_all_keys_present):
    result = asyncio.run(
        call_vision(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "x"}},
                        {"type": "text", "text": "describe"},
                    ],
                }
            ],
            task_name="vision-happy",
        )
    )
    # First vision entry is gemini/gemini-1.5-flash.
    assert result.provider_used == "gemini"
    assert result.model_used == "gemini-1.5-flash"


def test_call_embed_uses_embed_chain(_all_keys_present):
    result = asyncio.run(
        call_embed(
            inputs=["hello", "world"],
            task_name="embed-happy",
        )
    )
    assert result.provider_used == PROVIDERS["embed"][0].provider
    assert result.model_used == PROVIDERS["embed"][0].model
    assert "count=2" in result.content


# ---------- chain fallback ----------


def test_chain_falls_through_on_failure(
    _all_keys_present, monkeypatch: pytest.MonkeyPatch
):
    """Inject failure on groq -> chain should advance to cerebras (next in list)."""
    monkeypatch.setenv("MOCK_FAIL_PROVIDERS", "groq")
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="text-fallthrough",
        )
    )
    # First non-groq entry is cerebras/llama3.1-70b.
    assert result.provider_used == "cerebras"
    # chain_attempted records every failure before success.
    assert result.chain_attempted[0].startswith("groq/")
    assert result.chain_attempted[-1].startswith("cerebras/")


def test_chain_exhausted_raises(_all_keys_present, monkeypatch: pytest.MonkeyPatch):
    """Fail every provider in the text chain -> AllProvidersExhaustedError."""
    fail_set = ",".join({e.provider for e in PROVIDERS["text"]})
    monkeypatch.setenv("MOCK_FAIL_PROVIDERS", fail_set)
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        asyncio.run(
            call_text(
                messages=[{"role": "user", "content": "hi"}],
                task_name="text-exhausted",
            )
        )
    err = exc_info.value
    assert len(err.chain_attempted) == len(PROVIDERS["text"])


def test_no_eligible_providers_raises_with_empty_chain(monkeypatch: pytest.MonkeyPatch):
    """No env vars set -> plan filters everything -> exhausted with empty chain."""
    for key in {e.env_var for entries in PROVIDERS.values() for e in entries}:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        asyncio.run(
            call_text(
                messages=[{"role": "user", "content": "hi"}],
                task_name="text-no-keys",
            )
        )
    assert exc_info.value.chain_attempted == []


# ---------- quota persistence ----------


def test_success_persists_quota_increment(_all_keys_present, tmp_path: Path):
    asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="quota-persist-success",
        )
    )
    state = quotas.load()
    key = quotas.key_of("groq", "llama-3.3-70b-versatile")
    assert key in state.entries
    assert state.entries[key].requests_used == 1
    assert state.entries[key].consecutive_failures == 0


def test_failure_persists_quota_increment(
    _all_keys_present, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MOCK_FAIL_PROVIDERS", "groq")
    asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="quota-persist-failure",
        )
    )
    state = quotas.load()
    failed_key = quotas.key_of("groq", "llama-3.3-70b-versatile")
    assert state.entries[failed_key].consecutive_failures == 1


def test_persist_quotas_false_skips_disk_write(
    _all_keys_present, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Allow callers (e.g. dashboard preview) to opt out of disk writes."""
    asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="no-persist",
            persist_quotas=False,
        )
    )
    quota_file = tmp_path / "quotas.json"
    assert not quota_file.exists()


# ---------- backend injection ----------


def test_explicit_backend_kwarg_overrides_singleton(_all_keys_present):
    """Caller-supplied backend wins over the registered singleton."""

    class _Tagged(MockBackend):
        name = "tagged"

        async def call_text_one(self, **kwargs):  # type: ignore[override]
            r = await super().call_text_one(**kwargs)
            r.content = f"<tagged>{r.content}"
            return r

    tagged = _Tagged()
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="explicit-backend",
            backend=tagged,
        )
    )
    assert result.content.startswith("<tagged>")


# ---------- LLM_ALLOW_PAID flag ----------


def test_allow_paid_overrides_missing_env(monkeypatch: pytest.MonkeyPatch):
    """When allow_paid=True, env-var presence isn't required to plan."""
    for key in {e.env_var for entries in PROVIDERS.values() for e in entries}:
        monkeypatch.delenv(key, raising=False)
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="allow-paid",
            allow_paid=True,
        )
    )
    # Mock backend doesn't care about real keys; routing succeeds.
    assert result.provider_used == PROVIDERS["text"][0].provider


# ---------- dry_run preserved ----------


def test_dry_run_returns_plan_not_result(_all_keys_present):
    plan_obj = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="dry-run",
            dry_run=True,
        )
    )
    # Plan, not Result: has options + chosen, no chain_attempted.
    assert hasattr(plan_obj, "options")
    assert hasattr(plan_obj, "chosen")
    assert not hasattr(plan_obj, "chain_attempted")
