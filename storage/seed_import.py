"""Load the curated JSON seed into the DB on every boot.

The seed file is the human-curated source for catalog corrections:
- a provider missing from the DB is imported;
- a provider whose seed entry CHANGED since it was last imported is re-saved
  from the seed (a new version, diffed like any other change), so a fix to
  `data/providers_seed.json` reaches a DB restored from the `data` branch;
- an unchanged seed entry never overwrites what a refresh learned since.
Seed fingerprints live in repository state so this survives restarts.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from domain.records import ProviderRecord
from storage.repository import Repository

logger = logging.getLogger(__name__)

SEED_STATE_NAMESPACE = "seed-import"


def _seed_fingerprint(record: ProviderRecord) -> str:
    canonical = json.dumps(record.content_fingerprint(), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _should_save(repo: Repository, record: ProviderRecord, seen: dict[str, str]) -> bool:
    """Save when the provider is new, or when its seed entry changed since last import."""
    if repo.get_provider(record.provider_id) is None:
        return True
    previous = seen.get(record.provider_id)
    # No stored fingerprint = the DB predates fingerprinting or holds a manual
    # record; adopt the current seed as the baseline without overwriting.
    return previous is not None and previous != _seed_fingerprint(record)


def import_seed(repo: Repository, path: str | Path) -> int:
    """Apply the seed file; returns how many providers were imported or updated."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    seen: dict[str, str] = dict(repo.get_state(SEED_STATE_NAMESPACE))
    applied = 0
    for row in payload:
        record = ProviderRecord.from_storage(row)
        if _should_save(repo, record, seen):
            repo.save_provider(record, source="seed")
            applied += 1
        seen[record.provider_id] = _seed_fingerprint(record)
    repo.put_state(SEED_STATE_NAMESPACE, seen)
    logger.info("seed_imported", extra={"count": applied, "total_in_file": len(payload)})
    return applied
