"""SQLite persistence for the canonical record history + change log + verify queue.

Append-only design — every re-scrape is a new row. Read paths always
filter to the latest row per `provider_id`.

DB location: `${RESOURCEOS_DB_PATH}` (default `data/resourceos.db`).
Migrations: `schema/migrations/*.sql` applied in lexicographic order.
The current schema head is `schema/VERSION`.

This module is the only place in the repo that imports `sqlite3`. The
agents and pipeline talk to it via the typed helpers below.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from agents.change_detector import ChangeReport
from agents.verifier import VerifyItem
from schema.records import ProviderRecord


REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "schema" / "migrations"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "resourceos.db"


# ---------- connection ----------


def db_path() -> Path:
    raw = os.environ.get("RESOURCEOS_DB_PATH")
    return Path(raw) if raw else DEFAULT_DB_PATH


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite DB. Always returns a Connection with
    `row_factory = sqlite3.Row` and foreign keys enabled.
    """
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """`with db_session() as conn: ...` — closes on exit."""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


# ---------- migrations ----------


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchall()
    if not rows:
        return set()
    return {row["version"] for row in conn.execute("SELECT version FROM schema_version")}


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every `schema/migrations/NNN_*.sql` not yet recorded.

    Returns the list of versions newly applied.
    """
    applied = applied_versions(conn)
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    newly_applied: list[int] = []
    for path in sql_files:
        # Filename convention: 001_initial.sql -> version 1
        name = path.name
        try:
            version = int(name.split("_", 1)[0])
        except ValueError:
            continue
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(tz=timezone.utc).isoformat()),
        )
        newly_applied.append(version)
    return newly_applied


# ---------- ProviderRecord persistence ----------


def _record_to_row(record: ProviderRecord) -> tuple[Any, ...]:
    return (
        record.id,
        record.provider_id,
        record.provider_name,
        record.category,
        record.subcategory,
        record.source_url,
        record.offer_type,
        record.offer_summary,
        record.headline,
        record.currency,
        record.credit_amount,
        record.credit_duration_days,
        json.dumps(record.limits, sort_keys=True),
        record.quota_summary,
        record.duration_summary,
        record.region_summary,
        record.eligibility_summary,
        record.access_method,
        record.eligibility.model_dump_json(),
        record.restrictions,
        record.geo_priority,
        1 if record.india_accessible else 0,
        json.dumps(list(record.use_case_tiers)),
        record.tier_fit_rationale,
        record.scraped_at.isoformat(),
        record.parse_confidence,
        record.source_method,
        record.last_verified_at.isoformat() if record.last_verified_at else None,
        record.expiry_date.isoformat() if record.expiry_date else None,
        record.status,
        record.supersedes_id,
        record.notes,
    )


_INSERT_RECORD_SQL = """
INSERT INTO provider_records (
    id, provider_id, provider_name, category, subcategory, source_url,
    offer_type, offer_summary, headline, currency, credit_amount,
    credit_duration_days, limits_json,
    quota_summary, duration_summary, region_summary, eligibility_summary,
    access_method, eligibility_json, restrictions,
    geo_priority, india_accessible, use_case_tiers_json, tier_fit_rationale,
    scraped_at, parse_confidence, source_method, last_verified_at, expiry_date,
    status, supersedes_id, notes
) VALUES (?, ?, ?, ?, ?, ?,
          ?, ?, ?, ?, ?,
          ?, ?,
          ?, ?, ?, ?,
          ?, ?, ?,
          ?, ?, ?, ?,
          ?, ?, ?, ?, ?,
          ?, ?, ?)
ON CONFLICT(id) DO NOTHING
"""


def insert_record(conn: sqlite3.Connection, record: ProviderRecord) -> bool:
    """Insert a record. Idempotent on `id`. Returns True iff a new row was inserted."""
    cur = conn.execute(_INSERT_RECORD_SQL, _record_to_row(record))
    return cur.rowcount > 0


def insert_records(conn: sqlite3.Connection, records: list[ProviderRecord]) -> int:
    """Insert many. Returns count of rows actually inserted."""
    inserted = 0
    for r in records:
        if insert_record(conn, r):
            inserted += 1
    return inserted


def _row_to_record(row: sqlite3.Row) -> ProviderRecord:
    from datetime import date as _date

    payload = {
        "id": row["id"],
        "provider_id": row["provider_id"],
        "provider_name": row["provider_name"],
        "category": row["category"],
        "subcategory": row["subcategory"],
        "source_url": row["source_url"],
        "offer_type": row["offer_type"],
        "offer_summary": row["offer_summary"],
        "headline": row["headline"],
        "currency": row["currency"],
        "credit_amount": row["credit_amount"],
        "credit_duration_days": row["credit_duration_days"],
        "limits": json.loads(row["limits_json"] or "{}"),
        "quota_summary": row["quota_summary"],
        "duration_summary": row["duration_summary"],
        "region_summary": row["region_summary"],
        "eligibility_summary": row["eligibility_summary"],
        "access_method": row["access_method"],
        "eligibility": json.loads(row["eligibility_json"]),
        "restrictions": row["restrictions"],
        "geo_priority": row["geo_priority"],
        "india_accessible": bool(row["india_accessible"]),
        "use_case_tiers": json.loads(row["use_case_tiers_json"] or "[]"),
        "tier_fit_rationale": row["tier_fit_rationale"],
        "scraped_at": datetime.fromisoformat(row["scraped_at"]),
        "parse_confidence": row["parse_confidence"],
        "source_method": row["source_method"],
        "last_verified_at": _date.fromisoformat(row["last_verified_at"])
        if row["last_verified_at"]
        else None,
        "expiry_date": _date.fromisoformat(row["expiry_date"])
        if row["expiry_date"]
        else None,
        "status": row["status"],
        "supersedes_id": row["supersedes_id"],
        "notes": row["notes"],
    }
    return ProviderRecord.model_validate(payload)


def get_record(conn: sqlite3.Connection, record_id: str) -> ProviderRecord | None:
    row = conn.execute(
        "SELECT * FROM provider_records WHERE id = ?", (record_id,)
    ).fetchone()
    return _row_to_record(row) if row else None


def latest_records(conn: sqlite3.Connection) -> list[ProviderRecord]:
    """Return the latest row per provider_id, ordered by provider_id."""
    rows = conn.execute(
        """
        SELECT * FROM provider_records pr
        WHERE pr.scraped_at = (
            SELECT MAX(scraped_at) FROM provider_records
            WHERE provider_id = pr.provider_id
        )
        ORDER BY pr.provider_id
        """
    ).fetchall()
    return [_row_to_record(r) for r in rows]


def latest_for(
    conn: sqlite3.Connection, provider_id: str
) -> ProviderRecord | None:
    row = conn.execute(
        """
        SELECT * FROM provider_records
        WHERE provider_id = ?
        ORDER BY scraped_at DESC
        LIMIT 1
        """,
        (provider_id,),
    ).fetchone()
    return _row_to_record(row) if row else None


def history_for(
    conn: sqlite3.Connection, provider_id: str, *, limit: int = 50
) -> list[ProviderRecord]:
    rows = conn.execute(
        """
        SELECT * FROM provider_records
        WHERE provider_id = ?
        ORDER BY scraped_at DESC
        LIMIT ?
        """,
        (provider_id, limit),
    ).fetchall()
    return [_row_to_record(r) for r in rows]


# ---------- change reports ----------


def insert_change(conn: sqlite3.Connection, report: ChangeReport) -> int:
    """Append a change report row. Returns the new id."""
    cur = conn.execute(
        """
        INSERT INTO change_reports
            (provider_id, severity, changed_fields_json, summary,
             today_id, yesterday_id, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report.provider_id,
            report.severity,
            json.dumps(list(report.changed_fields)),
            report.summary,
            report.today_id,
            report.yesterday_id,
            datetime.now(tz=timezone.utc).isoformat(),
        ),
    )
    return cur.lastrowid or 0


def insert_changes(conn: sqlite3.Connection, reports: list[ChangeReport]) -> int:
    n = 0
    for r in reports:
        if insert_change(conn, r):
            n += 1
    return n


def latest_changes(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    severity: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent change reports as dicts (UI-ready)."""
    sql = "SELECT * FROM change_reports"
    params: tuple[Any, ...] = ()
    if severity:
        sql += " WHERE severity = ?"
        params = (severity,)
    sql += " ORDER BY detected_at DESC LIMIT ?"
    params = params + (limit,)
    rows = conn.execute(sql, params).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row["id"],
                "provider_id": row["provider_id"],
                "severity": row["severity"],
                "changed_fields": json.loads(row["changed_fields_json"]),
                "summary": row["summary"],
                "today_id": row["today_id"],
                "yesterday_id": row["yesterday_id"],
                "detected_at": row["detected_at"],
            }
        )
    return out


# ---------- verify queue ----------


def enqueue_verify(conn: sqlite3.Connection, item: VerifyItem) -> bool:
    """Insert a verify item. Idempotent on `record_id` — duplicates skipped."""
    cur = conn.execute(
        """
        INSERT INTO verify_queue
            (record_id, provider_id, provider_name, source_url,
             parse_confidence, reason, queued_at, record_payload_json,
             status, resolved_at, resolved_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(record_id) DO NOTHING
        """,
        (
            item.record_id,
            item.provider_id,
            item.provider_name,
            item.source_url,
            item.parse_confidence,
            item.reason,
            item.queued_at,
            json.dumps(item.record_payload, default=str),
            item.status,
            item.resolved_at,
            item.resolved_by,
        ),
    )
    return cur.rowcount > 0


def pending_verify(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM verify_queue WHERE status = 'pending' ORDER BY queued_at"
    ).fetchall()
    return [
        {
            "record_id": r["record_id"],
            "provider_id": r["provider_id"],
            "provider_name": r["provider_name"],
            "source_url": r["source_url"],
            "parse_confidence": r["parse_confidence"],
            "reason": r["reason"],
            "queued_at": r["queued_at"],
            "status": r["status"],
        }
        for r in rows
    ]


def resolve_verify(
    conn: sqlite3.Connection,
    record_id: str,
    *,
    status: str,
    resolved_by: str | None = None,
) -> bool:
    """Flip a pending row to confirmed/rejected/expired. Returns True iff updated."""
    if status not in ("confirmed", "rejected", "expired"):
        raise ValueError(
            f"status must be confirmed|rejected|expired, got {status!r}"
        )
    cur = conn.execute(
        """
        UPDATE verify_queue
           SET status = ?, resolved_at = ?, resolved_by = ?
         WHERE record_id = ? AND status = 'pending'
        """,
        (
            status,
            datetime.now(tz=timezone.utc).isoformat(),
            resolved_by,
            record_id,
        ),
    )
    return cur.rowcount > 0


def auto_expire_verify(conn: sqlite3.Connection, *, days: int = 30) -> int:
    """Mark every `pending` verify_queue row older than `days` days as `expired`.

    `resolved_by` is set to `"auto-expire"` so a human reviewer can
    distinguish auto-expired rows from confirmed/rejected ones.
    Idempotent: already-resolved rows are not touched (the WHERE clause
    requires `status='pending'`).

    Returns the count of rows updated.

    Closes architect roundtable CRITICAL #6 (2026-04-28): with the
    /verify UI killed in Sprint #3, low-confidence rows had no
    resolution path → unbounded growth on Render's free disk. This TTL
    sweep prevents that.
    """
    if days <= 0:
        raise ValueError(f"days must be a positive integer, got {days}")

    now = datetime.now(tz=timezone.utc)
    cutoff = (now - timedelta(days=days)).isoformat()
    cur = conn.execute(
        """
        UPDATE verify_queue
           SET status = 'expired',
               resolved_at = ?,
               resolved_by = 'auto-expire'
         WHERE status = 'pending'
           AND queued_at < ?
        """,
        (now.isoformat(), cutoff),
    )
    return cur.rowcount or 0


def verify_item_dict(item: VerifyItem) -> dict[str, Any]:
    """Helper for tests/printers."""
    return asdict(item)
