"""Starting and running a refresh — the `POST /api/refresh` background task."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from domain.runs import RefreshOptions, RunReport
from refresh.contracts import RefreshRunner
from storage.github_sync import DataSyncError, GitHubDataSync
from storage.repository import Repository

logger = logging.getLogger(__name__)

RunnerFactory = Callable[[Repository], RefreshRunner]


def new_run_id() -> str:
    """`run-<UTC timestamp>-<short random>` — sortable and collision-resistant."""
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run-{stamp}-{secrets.token_hex(3)}"


def start_run(repository: Repository, options: RefreshOptions) -> RunReport:
    """Create the run row (status `running`). Raises RunAlreadyActiveError if busy."""
    report = RunReport(run_id=new_run_id(), trigger="button", options=options)
    repository.create_run(report)
    return report


async def execute_and_sync(
    *,
    repository: Repository,
    report: RunReport,
    runner_factory: RunnerFactory,
    sync: GitHubDataSync | None,
    db_path: Path,
    on_synced: Callable[[datetime], None] | None = None,
) -> RunReport:
    """Run the refresh, then push the DB to the data branch on success.

    Never raises: any exception during the run or the push is recorded on
    the report (`status=failed`, `errors=[...]`) and persisted via
    `repository.update_run`, so the background task cannot crash silently.
    """
    try:
        runner = runner_factory(repository)
        report = await runner.run(report)
    except Exception as exc:  # noqa: BLE001 - last-resort guard, never leak to an unhandled task
        report = _mark_failed(report, exc)
        repository.update_run(report)
        return report

    if sync is not None:
        report = await _push_snapshot(repository, report, sync, db_path, on_synced)
    repository.update_run(report)
    return report


async def _push_snapshot(
    repository: Repository,
    report: RunReport,
    sync: GitHubDataSync,
    db_path: Path,
    on_synced: Callable[[datetime], None] | None,
) -> RunReport:
    """Snapshot the DB and push it; failures are recorded, never raised."""
    try:
        with TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / db_path.name
            _snapshot_to(repository, snapshot_path)
            await sync.push(snapshot_path, f"data: refresh {report.run_id}")
        synced_at = datetime.now(tz=timezone.utc)
        if on_synced is not None:
            on_synced(synced_at)
        return report.model_copy(update={"data_pushed": True})
    except Exception as exc:  # noqa: BLE001 - any push failure must still let update_run persist the run
        # Catching only DataSyncError left disk/SQLite/HTTP errors unhandled, so
        # the run stayed `running` and blocked the next refresh for 2 hours.
        logger.warning(
            "refresh_data_push_failed",
            extra={"run_id": report.run_id, "error_type": type(exc).__name__},
        )
        return report.model_copy(update={"errors": [*report.errors, f"data push failed: {exc}"]})


def _snapshot_to(repository: Repository, path: Path) -> None:
    """`Repository.snapshot_to` is SqliteRepository-only; call it defensively."""
    snapshot: Callable[[Path], None] | None = getattr(repository, "snapshot_to", None)
    if snapshot is None:
        raise DataSyncError("repository does not support snapshotting")
    snapshot(path)


def _mark_failed(report: RunReport, exc: Exception) -> RunReport:
    message = str(exc)  # never a token/secret: the exception here is runner-internal
    logger.error("refresh_run_failed", extra={"run_id": report.run_id, "error": message})
    return report.model_copy(
        update={
            "status": "failed",
            "finished_at": datetime.now(tz=timezone.utc),
            "errors": [*report.errors, message],
        }
    )


def default_runner_factory(repository: Repository) -> RefreshRunner:
    """Lazily import `refresh.runner` so this module works before it exists.

    `refresh.runner.create_runner` is being built in parallel; import it
    inside the call so a missing module only fails when a refresh is
    actually triggered, not at API import time.
    """
    from refresh.runner import create_runner  # noqa: PLC0415 - intentional lazy boundary

    return create_runner(repository)


__all__ = [
    "RunnerFactory",
    "default_runner_factory",
    "execute_and_sync",
    "new_run_id",
    "start_run",
]
