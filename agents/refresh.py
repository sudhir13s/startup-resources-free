"""Refresh agent — re-extract every existing DB row directly.

NO search-API calls. Walks the latest record per `provider_id`,
fetches its `source_url` via the polite client, optionally follows
1-2 internal links if the landing page lacks pricing signal, runs
the extractor, diffs vs the prior row, persists changes.

The key contract per the user: search APIs are spent on DISCOVERY
of net-new providers; refresh is purely a re-validation pass over
known sites. So this module imports nothing from `agents.search`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from agents.change_detector import diff_against_last
from agents.extractor import extract_record
from collectors.base import PoliteClient

logger = logging.getLogger(__name__)


# Pages most likely to carry the actual free-tier specs when the landing
# page is marketing-heavy. Tried in order; first hit wins.
FOLLOW_PATHS: tuple[str, ...] = (
    "/pricing",
    "/free",
    "/free-tier",
    "/startups",
    "/students",
    "/plans",
    "/developers",
)

# Tokens that indicate the page has pricing / free-tier signal.
# Cheap regex on rendered text, not a full classifier.
_PRICING_SIGNAL = re.compile(
    # Drop the leading \b so $-prefixed prices match (\b requires a
    # word/non-word transition, which $ at start-of-string doesn't have).
    r"(free\s+tier|free\s+forever|always\s+free|free\s+plan|"
    r"\$\s*0(\b|\s|$)|"
    r"\d+\s*(GB|MB|TB|hrs?|hours|requests|req(/|\s|$)|tokens))",
    re.IGNORECASE,
)


@dataclass
class RefreshSummary:
    started_at: str
    finished_at: str | None = None
    walked: int = 0
    changed: int = 0
    unchanged: int = 0
    extract_failed: int = 0
    fetch_failed: int = 0
    inserted_change_reports: int = 0
    pages_fetched: int = 0
    follow_hits: int = 0  # how often a follow-up page was needed
    snapshot_path: str | None = None
    db_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def has_pricing_signal(text: str) -> bool:
    return bool(_PRICING_SIGNAL.search(text or ""))


async def fetch_with_follows(
    client: PoliteClient,
    *,
    source_url: str,
    follow_paths: tuple[str, ...] = FOLLOW_PATHS,
    max_follows: int = 2,
) -> tuple[str, list[str]]:
    """Fetch `source_url`. If the body lacks pricing signal, try up to
    `max_follows` internal links from FOLLOW_PATHS. Returns the
    concatenated text of all fetched pages + the list of URLs hit.

    Concatenation lets the LLM extractor see all candidate signal in
    one shot — cheaper than running it on each page separately.
    """
    pages_visited: list[str] = []
    bodies: list[str] = []

    status, body, _ = await client.fetch(source_url)
    pages_visited.append(source_url)
    if status == 200 and body:
        bodies.append(body)

    if has_pricing_signal(body):
        return "\n\n---PAGE BREAK---\n\n".join(bodies), pages_visited

    follows_used = 0
    for path in follow_paths:
        if follows_used >= max_follows:
            break
        candidate = urljoin(source_url.rstrip("/") + "/", path.lstrip("/"))
        if candidate in pages_visited:
            continue
        try:
            s, b, _ = await client.fetch(candidate)
        except (httpx.HTTPError, OSError):
            continue
        pages_visited.append(candidate)
        if s == 200 and b:
            bodies.append(b)
            follows_used += 1
            if has_pricing_signal(b):
                break
    return "\n\n---PAGE BREAK---\n\n".join(bodies), pages_visited


async def refresh_all(
    *,
    db_path: Path | None = None,
    backend: Any = None,
    rate_limit_s: float | None = None,
    max_records: int | None = None,
) -> RefreshSummary:
    """Walk every latest-row in the DB, re-fetch + re-extract."""
    # Lazy import to keep CI / mock-mode free of the SQLite dependency.
    from backend import db as db_module  # type: ignore[import-untyped]

    summary = RefreshSummary(started_at=datetime.now(tz=timezone.utc).isoformat())

    conn = db_module.connect(db_path)
    db_module.apply_migrations(conn)
    summary.db_path = str(db_path) if db_path else None

    rows = db_module.latest_records(conn)
    if max_records is not None:
        rows = rows[:max_records]

    kwargs: dict[str, Any] = {}
    if rate_limit_s is not None:
        kwargs["rate_limit_s"] = rate_limit_s

    async with PoliteClient(**kwargs) as client:
        for record in rows:
            summary.walked += 1
            try:
                page_text, pages = await fetch_with_follows(
                    client, source_url=record.source_url
                )
                summary.pages_fetched += len(pages)
                if len(pages) > 1:
                    summary.follow_hits += 1
            except Exception as e:  # noqa: BLE001
                summary.fetch_failed += 1
                logger.warning(
                    "refresh:fetch_failed",
                    extra={
                        "provider_id": record.provider_id,
                        "url": record.source_url,
                        "error": str(e),
                    },
                )
                continue

            try:
                new_rec, _confidence, error = await extract_record(
                    page_text=page_text,
                    source_url=record.source_url,
                    task_name=f"refresh:{record.provider_id}",
                    backend=backend,
                )
            except Exception as e:  # noqa: BLE001
                summary.extract_failed += 1
                logger.exception(
                    "refresh:extract_crashed",
                    extra={"provider_id": record.provider_id, "error": str(e)},
                )
                continue

            if new_rec is None:
                summary.extract_failed += 1
                logger.info(
                    "refresh:extract_low_confidence",
                    extra={
                        "provider_id": record.provider_id,
                        "reason": error,
                    },
                )
                continue

            # Carry the SAME provider_id forward — the extractor may emit
            # a different slug if the page's wording differs. We trust
            # the existing slug.
            new_rec = new_rec.model_copy(
                update={"provider_id": record.provider_id, "supersedes_id": record.id}
            )

            report = diff_against_last(new_rec, record)
            if report.severity == "unchanged":
                summary.unchanged += 1
                continue

            if db_module.insert_record(conn, new_rec):
                summary.changed += 1
            if db_module.insert_change(conn, report):
                summary.inserted_change_reports += 1

    summary.finished_at = datetime.now(tz=timezone.utc).isoformat()
    conn.close()
    return summary


def write_summary(summary: RefreshSummary, *, out_dir: str | None = None) -> str:
    import json

    base = (
        Path(out_dir)
        if out_dir
        else Path(__file__).resolve().parent.parent / "data" / "refresh_runs"
    )
    base.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=timezone.utc).date().isoformat()
    path = base / f"{today}.json"
    path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return str(path)


# Re-export for cron entry-point convenience
__all__ = ["RefreshSummary", "refresh_all", "write_summary", "has_pricing_signal"]
