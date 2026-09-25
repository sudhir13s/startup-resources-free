"""Persistent per-provider per-day quota + cooldown tracker.

State is a small JSON blob namespaced as `"freellm"`, read/written through a
`StateStore` Protocol so the host application can inject its own persistence
(e.g. a SQLite-backed repository) without freellm importing that package.

Default store: `JsonFileStateStore`, writing to
`${FREELLM_QUOTA_DIR}/quotas.json` (defaults to `data/freellm/quotas.json`
relative to cwd) — unchanged on-disk behavior from v0.1/v0.2.

Test store: `MemoryStateStore`, in-process dict, no disk I/O.

Callers that want a different backing (e.g. the FastAPI service injecting
its SQLite repository) call `freellm.configure(state_store=...)` once at
startup. The injected object only needs to structurally satisfy
`get_state(namespace: str) -> dict` / `put_state(namespace: str, data: dict)
-> None` — freellm never imports the concrete class.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

NAMESPACE = "freellm"


@runtime_checkable
class StateStore(Protocol):
    """Structural contract for quota persistence. See module docstring."""

    def get_state(self, namespace: str) -> dict: ...

    def put_state(self, namespace: str, data: dict) -> None: ...


def _quota_path() -> Path:
    base = os.environ.get("FREELLM_QUOTA_DIR")
    if base:
        return Path(base) / "quotas.json"
    return Path("data") / "freellm" / "quotas.json"


class JsonFileStateStore:
    """Default store — one JSON file on disk. Safe for a single process."""

    def get_state(self, namespace: str) -> dict:
        path = _quota_path()
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw.get(namespace, {})

    def put_state(self, namespace: str, data: dict) -> None:
        path = _quota_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        existing[namespace] = data
        path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")


class MemoryStateStore:
    """In-process store — no disk I/O. Used by tests and dry-run callers."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def get_state(self, namespace: str) -> dict:
        return self._data.get(namespace, {})

    def put_state(self, namespace: str, data: dict) -> None:
        self._data[namespace] = data


_store: StateStore | None = None


def configure(*, state_store: StateStore | None) -> None:
    """Inject a custom StateStore (e.g. the API's SQLite repository).

    Pass None to reset to the default `JsonFileStateStore`.
    """
    global _store
    _store = state_store


def _resolve_store() -> StateStore:
    return _store if _store is not None else JsonFileStateStore()


@dataclass
class ProviderUsage:
    date: str  # ISO YYYY-MM-DD
    requests_used: int = 0
    tokens_used: int = 0
    consecutive_failures: int = 0
    last_success_at: str | None = None
    last_failure_reason: str | None = None
    disabled_until: str | None = None  # ISO date — auth failures
    cooldown_until: str | None = None  # ISO datetime — rate-limit backoff


@dataclass
class QuotaState:
    """In-memory working copy of the namespace's JSON blob.

    Keyed by `f"{provider}:{model}"`.
    """

    entries: dict[str, ProviderUsage] = field(default_factory=dict)


def _today() -> str:
    return datetime.now(tz=timezone.utc).date().isoformat()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def load() -> QuotaState:
    raw = _resolve_store().get_state(NAMESPACE)
    entries = {
        key: ProviderUsage(**val) for key, val in raw.get("entries", {}).items()
    }
    return QuotaState(entries=entries)


def save(state: QuotaState) -> None:
    payload = {"entries": {key: asdict(val) for key, val in state.entries.items()}}
    _resolve_store().put_state(NAMESPACE, payload)


def key_of(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def get(state: QuotaState, provider: str, model: str) -> ProviderUsage:
    key = key_of(provider, model)
    if key not in state.entries:
        state.entries[key] = ProviderUsage(date=_today())
    return state.entries[key]


def _roll_day_if_needed(usage: ProviderUsage) -> None:
    today = _today()
    if usage.date != today:
        usage.date = today
        usage.requests_used = 0
        usage.tokens_used = 0


def record_success(
    state: QuotaState,
    *,
    provider: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    usage = get(state, provider, model)
    _roll_day_if_needed(usage)
    usage.requests_used += 1
    usage.tokens_used += tokens_in + tokens_out
    usage.consecutive_failures = 0
    usage.cooldown_until = None
    usage.last_success_at = _now().isoformat()


def record_failure(
    state: QuotaState,
    *,
    provider: str,
    model: str,
    reason: str,
    auto_disable_after: int = 3,
) -> None:
    """Generic failure path — used for transient/request errors.

    Rate-limit failures go through `record_cooldown` instead, which sets
    `cooldown_until` rather than the permanent `disabled_until`.
    """
    usage = get(state, provider, model)
    _roll_day_if_needed(usage)
    usage.requests_used += 1
    usage.consecutive_failures += 1
    usage.last_failure_reason = reason
    if usage.consecutive_failures >= auto_disable_after:
        # Disable for the rest of today; a future success clears it.
        usage.disabled_until = _today()


def record_cooldown(
    state: QuotaState,
    *,
    provider: str,
    model: str,
    reason: str,
    cooldown_until: datetime,
) -> None:
    """Rate-limit (429) path — cools this provider:model down until a
    specific time instead of disabling it outright. Router skips entries
    whose `cooldown_until` is in the future.
    """
    usage = get(state, provider, model)
    _roll_day_if_needed(usage)
    usage.requests_used += 1
    usage.last_failure_reason = reason
    usage.cooldown_until = cooldown_until.isoformat()


def record_auth_disable(
    state: QuotaState, *, provider: str, model: str, reason: str
) -> None:
    """401/403 path — disable for the rest of the process's day. A bad key
    won't fix itself on retry, so there is no cooldown expiry, only a
    same-day disable (an operator fixing the key restarts the process).
    """
    usage = get(state, provider, model)
    _roll_day_if_needed(usage)
    usage.requests_used += 1
    usage.last_failure_reason = reason
    usage.disabled_until = _today()


def is_disabled(usage: ProviderUsage) -> bool:
    if usage.disabled_until is None:
        return False
    return usage.disabled_until >= _today()


def is_cooling_down(usage: ProviderUsage) -> bool:
    if usage.cooldown_until is None:
        return False
    try:
        until = datetime.fromisoformat(usage.cooldown_until)
    except ValueError:
        return False
    return until > _now()


def remaining_hint(usage: ProviderUsage) -> str:
    """Short human-readable string for plan/CLI output."""
    if is_disabled(usage):
        return f"disabled until {usage.disabled_until}"
    if is_cooling_down(usage):
        return f"cooling down until {usage.cooldown_until}"
    return f"{usage.requests_used} req used today"
