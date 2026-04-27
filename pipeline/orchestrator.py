"""End-to-end orchestrator — collectors → agents → DB → snapshot.

Phases:

    1. fetch        polite-fetch each collector's source URL
    2. extract      LLM extractor (agents.extractor) OR heuristic (collector.extract_fields)
    3. classify     LLM tier_classifier when in llm mode
    4. diff         change_detector against the latest DB row per provider_id
    5. persist      insert records + change reports + verify queue
    6. snapshot     write data/snapshots/<date>.json (legacy FE compat)

Modes:
    - "heuristic"  no LLM. Falls back to seed-merge for unparsed fields.
                   Used in CI and when no provider keys are present.
    - "llm"        full LLM pipeline. Requires at least one freellm key.
    - "auto"       try llm; on AllProvidersExhaustedError downgrade
                   that record to heuristic.

Lock files at `data/runs/<run-id>.lock` prevent double-runs (cron + manual).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from agents.change_detector import ChangeReport, diff_against_last  # noqa: E402
from agents.extractor import extract_record  # noqa: E402
from agents.tier_classifier import assign_tiers  # noqa: E402
from agents.verifier import VerifyItem  # noqa: E402
from collectors import REGISTRY, BaseCollector, FetchResult, PoliteClient  # noqa: E402
from schema.records import ProviderRecord, record_from_seed  # noqa: E402

import db as db_module  # type: ignore[import-untyped]  # noqa: E402
import snapshots as snap_module  # noqa: E402

logger = logging.getLogger("pipeline.orchestrator")

Mode = Literal["heuristic", "llm", "auto"]

SEED_PATH = REPO_ROOT / "data" / "seed.json"
RUNS_DIR = REPO_ROOT / "data" / "runs"


# ---------- run summary ----------


@dataclass
class ProviderSummary:
    provider_id: str
    status_code: int | None = None
    not_modified: bool = False
    raw_path: str | None = None
    parse_confidence: str | None = None
    record_id: str | None = None
    change_severity: str | None = None
    error: str | None = None
    mode_used: Mode = "heuristic"


@dataclass
class RunSummary:
    started_at: str
    finished_at: str | None = None
    mode: Mode = "auto"
    snapshot_path: str | None = None
    provider_summaries: list[ProviderSummary] = field(default_factory=list)
    db_path: str | None = None
    inserted_records: int = 0
    inserted_changes: int = 0
    queued_for_verify: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "mode": self.mode,
            "db_path": self.db_path,
            "snapshot_path": self.snapshot_path,
            "totals": {
                "providers": len(self.provider_summaries),
                "inserted_records": self.inserted_records,
                "inserted_changes": self.inserted_changes,
                "queued_for_verify": self.queued_for_verify,
            },
            "providers": [s.__dict__ for s in self.provider_summaries],
        }


# ---------- helpers ----------


def _load_seed_index() -> dict[str, dict[str, Any]]:
    if not SEED_PATH.exists():
        return {}
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {r["id"]: r for r in rows}


def _detect_provider_keys_present() -> bool:
    """Cheap heuristic for `mode='auto'` — any free provider env var set?"""
    common = (
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "CEREBRAS_API_KEY",
        "TOGETHER_API_KEY",
        "MISTRAL_API_KEY",
        "HF_TOKEN",
    )
    return any(os.environ.get(k) for k in common)


def _resolved_mode(requested: Mode) -> Mode:
    if requested != "auto":
        return requested
    return "llm" if _detect_provider_keys_present() else "heuristic"


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------- single-provider runners ----------


async def _heuristic_record(
    collector: BaseCollector,
    fr: FetchResult,
    seed_idx: dict[str, dict[str, Any]],
) -> ProviderRecord | None:
    """Heuristic path: collector.extract_fields() + merge with seed.

    The legacy v0.1 path. We still adapt the merged dict into a real
    ProviderRecord so the rest of the pipeline only deals with one shape.
    """
    extracted = collector.extract_fields(fr.text) if fr.text else None
    seed_row = seed_idx.get(collector.provider_id)
    if extracted is None and seed_row is None:
        return None
    merged = dict(seed_row or {})
    if extracted:
        for k, v in extracted.items():
            if v not in (None, ""):
                merged[k] = v
    if "id" not in merged:
        return None
    try:
        return record_from_seed(merged)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "heuristic merge failed for %s: %s", collector.provider_id, e
        )
        return None


async def _llm_record(
    collector: BaseCollector,
    fr: FetchResult,
    *,
    backend: Any = None,
) -> tuple[ProviderRecord | None, str, str | None]:
    """LLM path: agents.extractor + agents.tier_classifier.

    Returns (record, parse_confidence, error). On full chain exhaustion
    record is None; caller decides whether to fall back to heuristic.
    """
    record, confidence, error = await extract_record(
        page_text=fr.text or "",
        source_url=collector.source_url,
        task_name=f"extract:{collector.provider_id}",
        backend=backend,
    )
    if record is None:
        return None, confidence, error
    record = await assign_tiers(
        record, task_name=f"tier:{collector.provider_id}", backend=backend
    )
    return record, record.parse_confidence, None


# ---------- main entry ----------


async def run_pipeline(
    *,
    only: list[str] | None = None,
    mode: Mode = "auto",
    rate_limit_s: float | None = None,
    db_path: Path | None = None,
    write_snapshot: bool = True,
    backend: Any = None,
) -> RunSummary:
    """Run the orchestrator end-to-end.

    `db_path=None` means "no DB writes" (used by tests + dry-run-ish flows).
    Pass `Path(":memory:")` to use an in-memory DB.
    """
    summary = RunSummary(started_at=_utcnow_iso(), mode=mode)
    chosen: list[BaseCollector] = REGISTRY.all()
    if only:
        only_set = set(only)
        chosen = [c for c in chosen if c.provider_id in only_set]
    if not chosen:
        summary.finished_at = _utcnow_iso()
        return summary

    resolved_mode = _resolved_mode(mode)
    summary.mode = resolved_mode
    seed_idx = _load_seed_index()
    # `requested_mode` keeps the caller's intent (auto vs llm vs heuristic);
    # `resolved_mode` is what we actually attempt first per provider. Auto
    # mode falls back to heuristic when the LLM emits unparseable output —
    # llm-only does not.
    requested_mode = mode

    # Open DB once (or skip).
    conn: sqlite3.Connection | None = None
    if db_path is not None:
        conn = db_module.connect(db_path)
        db_module.apply_migrations(conn)
        summary.db_path = str(db_path)

    fetched: list[ProviderRecord] = []
    kwargs: dict[str, Any] = {}
    if rate_limit_s is not None:
        kwargs["rate_limit_s"] = rate_limit_s
    async with PoliteClient(**kwargs) as client:
        for c in chosen:
            ps = ProviderSummary(provider_id=c.provider_id, mode_used=resolved_mode)
            try:
                fr = await c.collect(client)
                ps.status_code = fr.status_code
                ps.not_modified = fr.not_modified
                if fr.raw_path:
                    ps.raw_path = str(fr.raw_path)

                record: ProviderRecord | None = None
                if resolved_mode in ("llm", "auto") and fr.is_ok and fr.text:
                    rec, confidence, error = await _llm_record(
                        c, fr, backend=backend
                    )
                    if rec is not None:
                        record = rec
                        ps.parse_confidence = confidence
                    elif requested_mode == "auto":
                        # downgrade THIS provider to heuristic
                        record = await _heuristic_record(c, fr, seed_idx)
                        ps.parse_confidence = (
                            record.parse_confidence if record else None
                        )
                        ps.mode_used = "heuristic"
                    else:
                        ps.error = error
                else:
                    record = await _heuristic_record(c, fr, seed_idx)
                    if record is not None:
                        ps.parse_confidence = record.parse_confidence

                if record is not None:
                    fetched.append(record)
                    ps.record_id = record.id
                    if conn is not None:
                        # Diff vs latest in DB (None = first time we've seen it).
                        prior = db_module.latest_for(conn, record.provider_id)
                        report: ChangeReport = diff_against_last(record, prior)
                        if db_module.insert_record(conn, record):
                            summary.inserted_records += 1
                        if db_module.insert_change(conn, report):
                            summary.inserted_changes += 1
                        ps.change_severity = report.severity
                        if record.parse_confidence == "low":
                            item = VerifyItem(
                                record_id=record.id,
                                provider_id=record.provider_id,
                                provider_name=record.provider_name,
                                source_url=record.source_url,
                                parse_confidence=record.parse_confidence,
                                reason=ps.error or "low-confidence extraction",
                                queued_at=_utcnow_iso(),
                                record_payload=record.model_dump(mode="json"),
                            )
                            if db_module.enqueue_verify(conn, item):
                                summary.queued_for_verify += 1
            except Exception as e:  # noqa: BLE001 - top-level loop must not crash
                ps.error = str(e)
                logger.exception("collector %s failed", c.provider_id)
            summary.provider_summaries.append(ps)

    # Snapshot (legacy FE shape) — always write so the existing API has data.
    if write_snapshot:
        rows: list[dict[str, Any]]
        if fetched:
            rows = [r.to_seed_shape() for r in fetched]
            # Preserve seed entries we did NOT re-collect this run.
            collected_ids = {r.provider_id for r in fetched}
            for sid, srow in seed_idx.items():
                if sid not in collected_ids:
                    rows.append(srow)
        else:
            rows = list(seed_idx.values())
        snap_path = snap_module.write_snapshot(rows)
        summary.snapshot_path = str(snap_path)

    if conn is not None:
        with suppress(Exception):
            conn.close()

    summary.finished_at = _utcnow_iso()
    return summary


# ---------- lock files ----------


def _lock_path(run_id: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"{run_id}.lock"


def acquire_lock(run_id: str) -> Path | None:
    """Atomically create a lock file. Returns the path on success, None
    if a lock < 24h old already exists.
    """
    path = _lock_path(run_id)
    if path.exists():
        age_s = (
            datetime.now(tz=timezone.utc).timestamp()
            - path.stat().st_mtime
        )
        if age_s < 24 * 3600:
            return None
        path.unlink(missing_ok=True)
    try:
        path.touch(exist_ok=False)
    except FileExistsError:
        return None
    return path


def release_lock(path: Path) -> None:
    with suppress(FileNotFoundError):
        path.unlink()


def run_with_lock(coro_factory: Any, *, run_id: str) -> Any:
    """asyncio.run a coroutine factory under a lock file. Used by the CLI."""
    lock = acquire_lock(run_id)
    if lock is None:
        return {"error": "another run is in progress", "run_id": run_id}
    try:
        return asyncio.run(coro_factory())
    finally:
        release_lock(lock)
