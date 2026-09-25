"""FastAPI application factory — repository-backed API with on-demand refresh.

`create_app()` builds a fully wired app; a module-level `app` is created
only when this module is imported by uvicorn (`python -m api`, or
`uvicorn api.main:app`), never at plain `import api.main` time, so tests
can build their own isolated app via `create_app(...)`.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import candidates, changes, freellm_router, health, providers, refresh, runs
from api.services.refresh_service import RunnerFactory, default_runner_factory
from api.settings import Settings, load_settings
from storage.github_sync import DataSyncError, GitHubDataSync
from storage.repository import Repository
from storage.seed_import import import_seed
from storage.sqlite_repository import SqliteRepository

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)


def create_app(
    settings: Settings | None = None,
    repository: Repository | None = None,
    sync: GitHubDataSync | None = None,
    runner_factory: RunnerFactory | None = None,
) -> FastAPI:
    """Build the FastAPI app. Injectable seams (repository/sync/runner_factory)
    let tests skip the real data-branch pull/push and inject a fake runner.
    """
    resolved_settings = settings or load_settings()
    app = FastAPI(title="ResourceOS API", version="0.2.0", lifespan=_lifespan)
    app.state.settings = resolved_settings
    app.state.injected_repository = repository
    app.state.injected_sync = sync if sync is not None else _NOT_SET
    app.state.runner_factory = runner_factory or default_runner_factory
    app.state.background_tasks = set()
    app.state.data_synced_at = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    for router in (health.router, providers.router, changes.router, runs.router,
                   refresh.router, candidates.router, freellm_router.router):
        app.include_router(router)

    return app


_NOT_SET = object()  # distinguishes "no sync override passed" from "override = None"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Pull the DB, apply migrations, import missing seed rows, configure freellm."""
    settings: Settings = app.state.settings
    sync = app.state.injected_sync
    if sync is _NOT_SET:
        sync = settings.build_sync()
    app.state.sync = sync

    db_path = Path(settings.db_path)
    if sync is not None:
        await _pull_data(sync, db_path)

    repository = app.state.injected_repository or SqliteRepository(db_path)
    app.state.repository = repository
    imported = import_seed(repository, settings.seed_path)
    if imported:
        logger.info("startup_seed_imported", extra={"count": imported})

    import freellm  # noqa: PLC0415 - keep the module-level import surface small

    freellm.configure(state_store=repository)
    app.state.data_synced_at = datetime.now(tz=timezone.utc).isoformat() if sync is not None else None

    try:
        yield
    finally:
        for task in list(app.state.background_tasks):
            task.cancel()
        freellm.configure(state_store=None)  # never leave a closed repo as the global store
        if app.state.injected_repository is None:
            repository.close()
        if sync is not None:
            await sync.aclose()


async def _pull_data(sync: GitHubDataSync, db_path: Path) -> None:
    """Best-effort pull from the data branch — log and continue on failure
    (a fresh DB is then built from the seed file instead)."""
    try:
        pulled = await sync.pull(db_path)
        logger.info("startup_data_pull", extra={"pulled": pulled})
    except DataSyncError as exc:
        logger.warning("startup_data_pull_failed", extra={"error": str(exc)})


# Built only outside pytest: uvicorn imports `api.main:app` by string, so the
# module must expose a ready instance, but tests build isolated apps via
# `create_app(...)` with injected fakes and must never trigger real startup
# I/O (data-branch pull, real seed import) as an import side effect.
app: FastAPI | None = None
if "pytest" not in sys.modules:
    app = create_app()
