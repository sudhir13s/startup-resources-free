-- 001_v2.sql — ResourceOS v2 storage schema
--
-- Append-only version history per `docs/plans/architecture-v2/*modular-refresh-rebuild.md`
-- (Key decision 1: SQLite in git; Key decision 4: record v2 is vendor-offer shaped).
-- `provider_versions` is the source of truth (never UPDATE/DELETE a row);
-- `providers_current` is a materialized fast-read pointer to the latest
-- version per provider, updated in the same transaction as an insert.
--
-- Engine: SQLite, journal_mode=DELETE (single self-contained file — this
-- DB is committed to the git `data` branch, so no separate -wal/-shm
-- sidecar files can be left behind).

PRAGMA foreign_keys = ON;

-- =====================================================================
-- schema_version — tracks which migrations have been applied
-- =====================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- =====================================================================
-- provider_versions — append-only canonical record history
-- =====================================================================

CREATE TABLE IF NOT EXISTS provider_versions (
    provider_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    record_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    source TEXT NOT NULL,              -- seed|refresh|verify|candidate
    run_id TEXT,
    created_at TEXT NOT NULL,          -- ISO 8601 UTC
    PRIMARY KEY (provider_id, version)
);

CREATE INDEX IF NOT EXISTS idx_provider_versions_run_id
    ON provider_versions (run_id);

-- =====================================================================
-- providers_current — fast-read pointer to the latest version per offer
-- =====================================================================

CREATE TABLE IF NOT EXISTS providers_current (
    provider_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    record_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- =====================================================================
-- field_changes — reader-visible diffs, one row per FieldChange
-- =====================================================================

CREATE TABLE IF NOT EXISTS field_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL,
    run_id TEXT,
    change_json TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_field_changes_detected_at
    ON field_changes (detected_at DESC);

-- =====================================================================
-- runs — refresh run reports
-- =====================================================================

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,              -- running|succeeded|partial|failed
    started_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at
    ON runs (started_at DESC);

-- =====================================================================
-- candidates — discovery output awaiting Approve/Reject
-- =====================================================================

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending|approved|rejected|imported
    created_at TEXT NOT NULL,
    candidate_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_status
    ON candidates (status);

-- =====================================================================
-- verify_queue — low-confidence extractions awaiting a human decision
-- =====================================================================

CREATE TABLE IF NOT EXISTS verify_queue (
    item_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending|accepted|rejected|expired
    created_at TEXT NOT NULL,
    item_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verify_queue_status
    ON verify_queue (status);

-- =====================================================================
-- page_hashes — content-hash gate so an unchanged page skips the LLM
-- =====================================================================

CREATE TABLE IF NOT EXISTS page_hashes (
    url TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- =====================================================================
-- state — small JSON blobs (freellm/search-chain quota counters, etc.)
-- =====================================================================

CREATE TABLE IF NOT EXISTS state (
    namespace TEXT PRIMARY KEY,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
