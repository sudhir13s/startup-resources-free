"""SQLite implementation of `storage.repository.Repository`.

Single self-contained file (journal_mode=DELETE — no -wal/-shm sidecars),
because this DB is committed to the git `data` branch (Key decision 1,
architecture-v2 plan). One shared connection guarded by a lock: the API
runs a refresh in a background task while serving reads concurrently.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from domain.changes import FieldChange, diff_records
from domain.records import ProviderRecord
from domain.runs import Candidate, CandidateStatus, RunReport, VerifyItem, VerifyStatus
from storage.migrations import apply_migrations
from storage.repository import RunAlreadyActiveError, SaveResult, StoredVersion

logger = logging.getLogger(__name__)

STALE_RUN_AFTER = timedelta(hours=2)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _fingerprint(record: ProviderRecord) -> str:
    """sha256 of the content fingerprint — stable across freshness-only re-verifies."""
    payload = json.dumps(record.content_fingerprint(), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SqliteRepository:
    """Thread-safe SQLite-backed Repository. One connection, one lock."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = DELETE")
        self._conn.execute("PRAGMA foreign_keys = ON")
        with self._lock:
            applied = apply_migrations(self._conn, now_iso=_iso(_now()))
        if applied:
            logger.info("storage_migrations_applied", extra={"versions": applied})

    def close(self) -> None:
        """Close the underlying connection. Safe to call once, at shutdown."""
        with self._lock:
            self._conn.close()

    def snapshot_to(self, path: str | Path) -> None:
        """Write a consistent copy of the DB to `path` via VACUUM INTO (for the git push)."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn.execute("VACUUM INTO ?", (str(target),))

    # --- Catalog ---

    def list_providers(self) -> list[ProviderRecord]:
        """Latest version of every provider. `domain.taxonomy.Status` has no

        `deleted` value — an offer that is gone is represented as `status:
        "ended"` and stays visible (the UI marks it ended, per
        `diff_records`' "ended" severity); there is nothing to filter out.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT record_json FROM providers_current ORDER BY provider_id"
            ).fetchall()
        return [ProviderRecord.from_storage(json.loads(row["record_json"])) for row in rows]

    def get_provider(self, provider_id: str) -> ProviderRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT record_json FROM providers_current WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
        return ProviderRecord.from_storage(json.loads(row["record_json"])) if row else None

    def history(self, provider_id: str, limit: int = 20) -> list[StoredVersion]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT provider_id, version, record_json, source, run_id, created_at
                FROM provider_versions
                WHERE provider_id = ?
                ORDER BY version DESC
                LIMIT ?
                """,
                (provider_id, limit),
            ).fetchall()
        return [
            StoredVersion(
                provider_id=row["provider_id"],
                version=row["version"],
                record=ProviderRecord.from_storage(json.loads(row["record_json"])),
                source=row["source"],
                run_id=row["run_id"],
                created_at=_parse_dt(row["created_at"]),
            )
            for row in rows
        ]

    def save_provider(
        self, record: ProviderRecord, *, source: str, run_id: str | None = None
    ) -> SaveResult:
        """Append a new version only if the content fingerprint changed.

        A freshness-only re-verify (fingerprint unchanged) still updates
        `last_verified_at` / `scraped_at` / `parse_confidence` /
        `source_method` on both `providers_current` and the current
        `provider_versions` row, and returns `stored=False, changes=[]`.
        """
        fingerprint = _fingerprint(record)
        now_iso = _iso(_now())
        with self._lock:
            current_row = self._conn.execute(
                "SELECT version, record_json, fingerprint FROM providers_current WHERE provider_id = ?",
                (record.provider_id,),
            ).fetchone()  # providers_current.fingerprint mirrors the latest provider_versions row

            if current_row is not None and current_row["fingerprint"] == fingerprint:
                self._update_freshness(record, current_row["version"], now_iso)
                return SaveResult(stored=False, version=current_row["version"], changes=[])

            return self._store_new_version(record, current_row, fingerprint, source, run_id, now_iso)

    def _store_new_version(
        self,
        record: ProviderRecord,
        current_row: sqlite3.Row | None,
        fingerprint: str,
        source: str,
        run_id: str | None,
        now_iso: str,
    ) -> SaveResult:
        """Append the next version row and its pointer, then diff against the previous one."""
        previous = (
            ProviderRecord.from_storage(json.loads(current_row["record_json"]))
            if current_row is not None
            else None
        )
        new_version = (current_row["version"] + 1) if current_row is not None else 1
        record_json = json.dumps(record.to_storage())
        self._insert_version_row(record.provider_id, new_version, record_json, fingerprint, source, run_id, now_iso)
        changes = diff_records(previous, record, run_id=run_id, detected_at=_now())
        self._insert_changes(changes)
        return SaveResult(stored=True, version=new_version, changes=changes)

    def _insert_version_row(
        self,
        provider_id: str,
        version: int,
        record_json: str,
        fingerprint: str,
        source: str,
        run_id: str | None,
        now_iso: str,
    ) -> None:
        """Write the append-only history row and refresh the fast-read pointer."""
        self._conn.execute(
            "INSERT INTO provider_versions"
            " (provider_id, version, record_json, fingerprint, source, run_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (provider_id, version, record_json, fingerprint, source, run_id, now_iso),
        )
        self._conn.execute(
            """
            INSERT INTO providers_current (provider_id, version, record_json, fingerprint, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                version = excluded.version,
                record_json = excluded.record_json,
                fingerprint = excluded.fingerprint,
                updated_at = excluded.updated_at
            """,
            (provider_id, version, record_json, fingerprint, now_iso),
        )

    def _update_freshness(self, record: ProviderRecord, version: int, now_iso: str) -> None:
        """Refresh timestamp/confidence fields in place without a new version row."""
        current_row = self._conn.execute(
            "SELECT record_json FROM provider_versions WHERE provider_id = ? AND version = ?",
            (record.provider_id, version),
        ).fetchone()
        fresh = record.model_dump(mode="json")
        stored = json.loads(current_row["record_json"])
        for field in ("last_verified_at", "scraped_at", "parse_confidence", "source_method"):
            stored[field] = fresh[field]
        record_json = json.dumps(stored)
        self._conn.execute(
            "UPDATE provider_versions SET record_json = ? WHERE provider_id = ? AND version = ?",
            (record_json, record.provider_id, version),
        )
        self._conn.execute(
            "UPDATE providers_current SET record_json = ?, updated_at = ? WHERE provider_id = ?",
            (record_json, now_iso, record.provider_id),
        )

    # --- Changes feed ---

    def _insert_changes(self, changes: list[FieldChange]) -> None:
        for change in changes:
            self._conn.execute(
                "INSERT INTO field_changes (provider_id, run_id, change_json, detected_at) VALUES (?, ?, ?, ?)",
                (change.provider_id, change.run_id, change.model_dump_json(), _iso(change.detected_at)),
            )

    def list_changes(self, *, limit: int = 200, since: date | None = None) -> list[FieldChange]:
        sql = "SELECT change_json FROM field_changes"
        params: tuple[Any, ...] = ()
        if since is not None:
            sql += " WHERE detected_at >= ?"
            params = (since.isoformat(),)
        sql += " ORDER BY detected_at DESC LIMIT ?"
        params = params + (limit,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [FieldChange.model_validate_json(row["change_json"]) for row in rows]

    # --- Runs ---

    def create_run(self, report: RunReport) -> None:
        """Insert a run. Raises RunAlreadyActiveError if another run is `running` and fresh."""
        with self._lock:
            self._fail_stale_running_run()
            active = self._conn.execute(
                "SELECT run_id FROM runs WHERE status = 'running'"
            ).fetchone()
            if active is not None:
                raise RunAlreadyActiveError(f"run {active['run_id']} is already running")
            self._conn.execute(
                "INSERT INTO runs (run_id, status, started_at, report_json) VALUES (?, ?, ?, ?)",
                (report.run_id, report.status, _iso(report.started_at), report.model_dump_json()),
            )

    def _fail_stale_running_run(self) -> None:
        """Mark a `running` run older than STALE_RUN_AFTER as failed, so it stops blocking."""
        rows = self._conn.execute(
            "SELECT run_id, started_at, report_json FROM runs WHERE status = 'running'"
        ).fetchall()
        for row in rows:
            started = _parse_dt(row["started_at"])
            if _now() - started <= STALE_RUN_AFTER:
                continue
            report = RunReport.model_validate_json(row["report_json"])
            report = report.model_copy(
                update={
                    "status": "failed",
                    "finished_at": _now(),
                    "errors": [*report.errors, "stale run"],
                }
            )
            self._conn.execute(
                "UPDATE runs SET status = ?, report_json = ? WHERE run_id = ?",
                (report.status, report.model_dump_json(), report.run_id),
            )
            logger.warning("stale_run_failed", extra={"run_id": report.run_id})

    def update_run(self, report: RunReport) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status = ?, report_json = ? WHERE run_id = ?",
                (report.status, report.model_dump_json(), report.run_id),
            )

    def get_run(self, run_id: str) -> RunReport | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT report_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return RunReport.model_validate_json(row["report_json"]) if row else None

    def list_runs(self, limit: int = 20) -> list[RunReport]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT report_json FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [RunReport.model_validate_json(row["report_json"]) for row in rows]

    def active_run(self) -> RunReport | None:
        with self._lock:
            self._fail_stale_running_run()
            row = self._conn.execute(
                "SELECT report_json FROM runs WHERE status = 'running' LIMIT 1"
            ).fetchone()
        return RunReport.model_validate_json(row["report_json"]) if row else None

    # --- Discovery candidates ---

    def add_candidates(self, candidates: list[Candidate]) -> int:
        inserted = 0
        with self._lock:
            for candidate in candidates:
                cur = self._conn.execute(
                    """
                    INSERT INTO candidates (candidate_id, status, created_at, candidate_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(candidate_id) DO NOTHING
                    """,
                    (
                        candidate.candidate_id,
                        candidate.status,
                        _iso(candidate.created_at),
                        candidate.model_dump_json(),
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
        return inserted

    def list_candidates(self, status: CandidateStatus | None = "pending") -> list[Candidate]:
        sql = "SELECT candidate_json FROM candidates"
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [Candidate.model_validate_json(row["candidate_json"]) for row in rows]

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT candidate_json FROM candidates WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            if row is None:
                return
            candidate = Candidate.model_validate_json(row["candidate_json"]).model_copy(
                update={"status": status}
            )
            self._conn.execute(
                "UPDATE candidates SET status = ?, candidate_json = ? WHERE candidate_id = ?",
                (status, candidate.model_dump_json(), candidate_id),
            )

    # --- Verify queue ---

    @staticmethod
    def _verify_item_to_json(item: VerifyItem) -> str:
        """`proposed` is a ProviderRecord; its computed fields must go through to_storage()
        (plain model_dump_json would round-trip them back as forbidden `extra` input)."""
        payload = item.model_dump(mode="json")
        payload["proposed"] = item.proposed.to_storage()
        return json.dumps(payload)

    @staticmethod
    def _verify_item_from_json(raw: str) -> VerifyItem:
        payload = json.loads(raw)
        payload["proposed"] = ProviderRecord.from_storage(payload["proposed"])
        return VerifyItem.model_validate(payload)

    def enqueue_verify(self, item: VerifyItem) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO verify_queue (item_id, provider_id, status, created_at, item_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO NOTHING
                """,
                (item.item_id, item.provider_id, item.status, _iso(item.created_at), self._verify_item_to_json(item)),
            )

    def list_verify(self, status: VerifyStatus | None = "pending") -> list[VerifyItem]:
        sql = "SELECT item_json FROM verify_queue"
        params: tuple[Any, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._verify_item_from_json(row["item_json"]) for row in rows]

    def set_verify_status(self, item_id: str, status: VerifyStatus) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT item_json FROM verify_queue WHERE item_id = ?", (item_id,)
            ).fetchone()
            if row is None:
                return
            item = self._verify_item_from_json(row["item_json"]).model_copy(update={"status": status})
            self._conn.execute(
                "UPDATE verify_queue SET status = ?, item_json = ? WHERE item_id = ?",
                (status, self._verify_item_to_json(item), item_id),
            )

    # --- Page-hash gate ---

    def get_page_hash(self, url: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT content_hash FROM page_hashes WHERE url = ?", (url,)
            ).fetchone()
        return row["content_hash"] if row else None

    def set_page_hash(self, url: str, content_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO page_hashes (url, content_hash, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    updated_at = excluded.updated_at
                """,
                (url, content_hash, _iso(_now())),
            )

    # --- Small JSON state blobs ---

    def get_state(self, namespace: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data_json FROM state WHERE namespace = ?", (namespace,)
            ).fetchone()
        return json.loads(row["data_json"]) if row else {}

    def put_state(self, namespace: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO state (namespace, data_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(namespace) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_at = excluded.updated_at
                """,
                (namespace, json.dumps(data), _iso(_now())),
            )
