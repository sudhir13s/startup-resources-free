"""One-shot loader for a JSON seed file into a fresh (or partially-empty) DB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from domain.records import ProviderRecord
from storage.repository import Repository

logger = logging.getLogger(__name__)


def import_seed(repo: Repository, path: str | Path) -> int:
    """Load a JSON list of ProviderRecord dicts; save only providers missing from the DB.

    Idempotent: re-running against an already-seeded DB imports nothing,
    because every `provider_id` already present in `providers_current` is
    skipped before `save_provider` is called.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    imported = 0
    for row in payload:
        record = ProviderRecord.from_storage(row)
        if repo.get_provider(record.provider_id) is not None:
            continue
        repo.save_provider(record, source="seed")
        imported += 1
    logger.info("seed_imported", extra={"count": imported, "total_in_file": len(payload)})
    return imported
