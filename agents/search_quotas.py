"""Per-provider search-API quota tracking.

Persisted at `${SEARCH_QUOTA_DIR}/quotas.json` (defaults to
`data/search/quotas.json`). Mirrors the pattern in `freellm/quotas.py`
but for search providers (Tavily / Exa / Jina / Linkup / SerpAPI),
each with monthly caps that reset on the 1st.

Key model: a provider is "exhausted" for the rest of the calendar
month once `requests_used >= monthly_cap`. The chain falls through
to the next provider on exhaustion.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _quota_path() -> Path:
    base = os.environ.get("SEARCH_QUOTA_DIR")
    if base:
        return Path(base) / "quotas.json"
    return Path("data") / "search" / "quotas.json"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _current_month_key() -> str:
    """`YYYY-MM` — used to bucket usage and detect month rollover."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m")


@dataclass
class ProviderQuota:
    """One provider's running usage for the current calendar month."""

    name: str
    month_key: str  # YYYY-MM bucket; rolls over on the 1st
    monthly_cap: int  # 0 = effectively unlimited (e.g. Jina large quota)
    requests_used: int = 0
    last_success_at: str | None = None
    last_failure_reason: str | None = None
    consecutive_failures: int = 0

    def is_exhausted(self) -> bool:
        if self.monthly_cap == 0:
            return False
        return self.requests_used >= self.monthly_cap

    def remaining(self) -> int:
        if self.monthly_cap == 0:
            return 999_999
        return max(0, self.monthly_cap - self.requests_used)


@dataclass
class SearchQuotas:
    """All providers' usage."""

    entries: dict[str, ProviderQuota] = field(default_factory=dict)

    def get(self, name: str, monthly_cap: int) -> ProviderQuota:
        """Return the row for `name`, rolling over the month if needed."""
        current_month = _current_month_key()
        existing = self.entries.get(name)
        if existing is None or existing.month_key != current_month:
            self.entries[name] = ProviderQuota(
                name=name, month_key=current_month, monthly_cap=monthly_cap
            )
        return self.entries[name]

    def record_success(self, name: str, monthly_cap: int) -> ProviderQuota:
        q = self.get(name, monthly_cap)
        q.requests_used += 1
        q.last_success_at = _now_iso()
        q.consecutive_failures = 0
        return q

    def record_failure(
        self, name: str, monthly_cap: int, reason: str
    ) -> ProviderQuota:
        q = self.get(name, monthly_cap)
        q.requests_used += 1  # failed call still counts (most APIs charge regardless)
        q.consecutive_failures += 1
        q.last_failure_reason = reason[:200]
        return q

    def remaining_summary(self) -> dict[str, int]:
        return {name: q.remaining() for name, q in self.entries.items()}


def load() -> SearchQuotas:
    path = _quota_path()
    if not path.exists():
        return SearchQuotas()
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = {
        key: ProviderQuota(**val) for key, val in raw.get("entries", {}).items()
    }
    return SearchQuotas(entries=entries)


def save(state: SearchQuotas) -> None:
    path = _quota_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"entries": {k: asdict(v) for k, v in state.entries.items()}},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
