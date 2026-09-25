"""Applies numbered `storage/migrations/*.sql` files once, tracked in `schema_version`.

Filename convention: `001_v2.sql` -> version 1. Each `.sql` file runs inside
`executescript`, then its version is recorded so a later boot never re-runs it.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Versions already recorded in `schema_version` (empty set pre-bootstrap)."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if exists is None:
        return set()
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return {row[0] for row in rows}


def _version_from_filename(path: Path) -> int | None:
    """Extract the leading integer from `NNN_name.sql`, else None to skip it."""
    prefix = path.stem.split("_", 1)[0]
    return int(prefix) if prefix.isdigit() else None


def apply_migrations(conn: sqlite3.Connection, *, now_iso: str, directory: Path | None = None) -> list[int]:
    """Apply every unapplied `.sql` file in lexicographic order.

    Returns the list of versions newly applied (empty when the DB is current).
    """
    migrations_dir = directory or MIGRATIONS_DIR
    applied = _applied_versions(conn)
    newly_applied: list[int] = []
    for sql_path in sorted(migrations_dir.glob("*.sql")):
        version = _version_from_filename(sql_path)
        if version is None or version in applied:
            continue
        conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, now_iso),
        )
        newly_applied.append(version)
        logger.info("migration_applied", extra={"version": version, "file": sql_path.name})
    return newly_applied
