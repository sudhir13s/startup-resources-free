"""Router chain logic — exercised against MockBackend (no network)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from freellm import (
    PROVIDERS,
    AllProvidersExhaustedError,
    call_embed,
    call_text,
    call_vision,
    quotas,
    set_backend,
)
from freellm.backends.mock import MockBackend
from freellm.errors import AuthError, RateLimitedError
from freellm.schemas import Result


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
    # First text entry in catalog is groq/openai/gpt-oss-120b.
    assert result.provider_used == "groq"
    assert result.model_used == "openai/gpt-oss-120b"
    assert "hello" in result.content
    assert result.chain_attempted == ["groq/openai/gpt-oss-120b"]


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
    # First vision entry is gemini/gemini-2.5-flash.
    assert result.provider_used == "gemini"
    assert result.model_used == "gemini-2.5-flash"


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
    """Inject failure on groq -> chain should advance past both groq entries
    to gemini (next distinct provider in the list)."""
    monkeypatch.setenv("MOCK_FAIL_PROVIDERS", "groq")
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="text-fallthrough",
        )
    )
    # First non-groq entry is gemini/gemini-2.5-flash.
    assert result.provider_used == "gemini"
    # chain_attempted records every failure before success.
    assert result.chain_attempted[0].startswith("groq/")
    assert result.chain_attempted[-1].startswith("gemini/")


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
    key = quotas.key_of("groq", "openai/gpt-oss-120b")
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
    failed_key = quotas.key_of("groq", "openai/gpt-oss-120b")
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


# ---------- rate-limit rotation (429 -> cooldown -> next provider) ----------


class _TypedFailureBackend(MockBackend):
    """MockBackend variant that raises a specific typed error for one
    provider slug, then delegates to MockBackend for everyone else.
    """

    name = "typed-failure"

    def __init__(self, *, fail_provider: str, error: BaseException) -> None:
        self._fail_provider = fail_provider
        self._error = error

    async def call_text_one(self, *, provider: str, **kwargs: Any) -> Result:  # type: ignore[override]
        if provider == self._fail_provider:
            raise self._error
        return await super().call_text_one(provider=provider, **kwargs)


def test_rate_limit_falls_through_and_persists_cooldown(
    _all_keys_present, tmp_path: Path
):
    """429 on groq -> router advances to the next provider AND persists a
    cooldown_until so the NEXT plan() skips groq without retrying it.
    """
    backend = _TypedFailureBackend(
        fail_provider="groq",
        error=RateLimitedError("groq", "rate limited", retry_after_s=30),
    )
    set_backend(backend)
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="rate-limit-fallthrough",
        )
    )
    assert result.provider_used == "gemini"

    state = quotas.load()
    groq_key = quotas.key_of("groq", "openai/gpt-oss-120b")
    usage = state.entries[groq_key]
    assert usage.cooldown_until is not None
    assert quotas.is_cooling_down(usage)


def test_daily_exhaustion_cooldown_extends_past_short_backoff(
    _all_keys_present, tmp_path: Path
):
    """A 429 that looks like a daily-quota exhaustion cools the provider
    down past midnight UTC, not just a short RPM-style window.
    """
    backend = _TypedFailureBackend(
        fail_provider="groq",
        error=RateLimitedError(
            "groq", "daily quota exceeded", retry_after_s=5, daily_exhausted=True
        ),
    )
    set_backend(backend)
    asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="daily-exhaustion",
        )
    )
    state = quotas.load()
    usage = quotas.get(state, "groq", "openai/gpt-oss-120b")
    cooldown = datetime.fromisoformat(usage.cooldown_until)  # type: ignore[arg-type]
    # A daily cooldown must outlast a plain 5s retry-after window.
    assert cooldown > datetime.now(tz=timezone.utc) + timedelta(seconds=5)


def test_auth_error_disables_provider_for_the_day(_all_keys_present, tmp_path: Path):
    """401 -> the provider is disabled (not just cooled down) so a
    same-run retry never hits the bad key again.
    """
    backend = _TypedFailureBackend(
        fail_provider="groq", error=AuthError("groq", "invalid key")
    )
    set_backend(backend)
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="auth-disable",
        )
    )
    assert result.provider_used == "gemini"

    state = quotas.load()
    usage = quotas.get(state, "groq", "openai/gpt-oss-120b")
    assert quotas.is_disabled(usage)

    # A second plan() in the same "day" must skip groq entirely.
    p = _plan_after_reload()
    groq_option_keys = {opt.provider for opt in p.options}
    assert "groq" not in groq_option_keys


def _plan_after_reload():
    from freellm.router import plan as _plan

    return _plan(modality="text", task_name="post-disable-plan")


def test_plan_reflects_active_cooldown(_all_keys_present, tmp_path: Path):
    """plan() must skip a provider:model whose cooldown_until is in the
    future, and surface the reason in `reason_skipped`. A sibling model on
    the same provider (not cooled down) stays eligible.
    """
    state = quotas.load()
    quotas.record_cooldown(
        state,
        provider="groq",
        model="openai/gpt-oss-120b",
        reason="429",
        cooldown_until=datetime.now(tz=timezone.utc) + timedelta(seconds=120),
    )
    quotas.save(state)

    p = _plan_after_reload()
    assert all(
        (opt.provider, opt.model) != ("groq", "openai/gpt-oss-120b") for opt in p.options
    )
    assert any(("groq", "openai/gpt-oss-20b") == (opt.provider, opt.model) for opt in p.options)
    assert any("cooling down" in reason for reason in p.reason_skipped.values())


def test_plan_reflects_missing_env_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for key in {e.env_var for entries in PROVIDERS.values() for e in entries}:
        monkeypatch.delenv(key, raising=False)
    p = _plan_after_reload()
    assert p.options == []
    assert all("missing env var" in reason for reason in p.reason_skipped.values())


def test_never_retries_same_provider_twice_in_one_chain(
    _all_keys_present, tmp_path: Path
):
    """A provider:model that fails is attempted at most once per call — the
    router's retry strategy IS falling through, never a same-entry loop.
    (groq has two catalog entries — gpt-oss-120b and gpt-oss-20b — so both
    are legitimately attempted once each; neither repeats.)
    """
    backend = _TypedFailureBackend(
        fail_provider="groq",
        error=RateLimitedError("groq", "rate limited", retry_after_s=30),
    )
    set_backend(backend)
    result = asyncio.run(
        call_text(
            messages=[{"role": "user", "content": "hi"}],
            task_name="no-double-retry",
        )
    )
    groq_attempts = [t for t in result.chain_attempted if t.startswith("groq/")]
    assert len(groq_attempts) == len(set(groq_attempts))


# ---------- StateStore round-trip ----------


def test_json_file_state_store_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from freellm.quotas import JsonFileStateStore

    monkeypatch.setenv("FREELLM_QUOTA_DIR", str(tmp_path))
    store = JsonFileStateStore()
    assert store.get_state("freellm") == {}
    store.put_state("freellm", {"entries": {"groq:model-a": {"date": "2026-09-25"}}})
    reloaded = store.get_state("freellm")
    assert reloaded["entries"]["groq:model-a"]["date"] == "2026-09-25"


def test_memory_state_store_round_trip():
    from freellm.quotas import MemoryStateStore

    store = MemoryStateStore()
    assert store.get_state("freellm") == {}
    store.put_state("freellm", {"entries": {"x": 1}})
    assert store.get_state("freellm") == {"entries": {"x": 1}}


def test_configure_injects_custom_state_store(tmp_path: Path):
    """`freellm.configure(state_store=...)` swaps quota persistence without
    freellm importing the injected class — a plain object structurally
    matching `get_state`/`put_state` is enough.
    """
    import freellm
    from freellm.quotas import MemoryStateStore

    custom_store = MemoryStateStore()
    freellm.configure(state_store=custom_store)
    try:
        state = quotas.load()
        quotas.record_success(state, provider="groq", model="m", tokens_in=1, tokens_out=1)
        quotas.save(state)
        assert custom_store.get_state("freellm")["entries"]
    finally:
        freellm.configure(state_store=None)
