-- 001_initial.sql — base schema for ResourceOS
--
-- Append-only history (per `.claude/rules/project/provider-schema.md`):
-- a re-scrape produces a NEW row in `provider_records` pointing at the
-- previous via `supersedes_id`. We never UPDATE a record in place; that
-- way the dashboard's Changes tab can reconstruct any past day.
--
-- Engine: SQLite. The same schema migrates cleanly to Postgres later
-- (only enum-as-text + INTEGER-as-bool need adjustment); we intentionally
-- avoid SQLite-specific features.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- =====================================================================
-- schema_version — single-row table tracking the highest applied migration
-- =====================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- =====================================================================
-- provider_records — append-only canonical record history
-- =====================================================================

CREATE TABLE IF NOT EXISTS provider_records (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    source_url TEXT NOT NULL,

    offer_type TEXT NOT NULL,
    offer_summary TEXT NOT NULL,
    headline TEXT,
    currency TEXT,
    credit_amount REAL,
    credit_duration_days INTEGER,
    limits_json TEXT NOT NULL DEFAULT '{}',

    quota_summary TEXT NOT NULL,
    duration_summary TEXT NOT NULL,
    region_summary TEXT NOT NULL,
    eligibility_summary TEXT NOT NULL,

    access_method TEXT NOT NULL,
    eligibility_json TEXT NOT NULL,
    restrictions TEXT,

    geo_priority TEXT NOT NULL,
    india_accessible INTEGER NOT NULL,            -- 0/1 boolean
    use_case_tiers_json TEXT NOT NULL DEFAULT '[]',
    tier_fit_rationale TEXT,

    scraped_at TEXT NOT NULL,                      -- ISO 8601 UTC
    parse_confidence TEXT NOT NULL,                -- high|medium|low
    source_method TEXT NOT NULL,                   -- api|rss|...|llm|manual
    last_verified_at TEXT,                         -- ISO date
    expiry_date TEXT,                              -- ISO date

    status TEXT NOT NULL DEFAULT 'active',
    supersedes_id TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_provider_records_provider_id
    ON provider_records (provider_id);
CREATE INDEX IF NOT EXISTS idx_provider_records_scraped_at
    ON provider_records (scraped_at);
CREATE INDEX IF NOT EXISTS idx_provider_records_provider_id_scraped_at
    ON provider_records (provider_id, scraped_at DESC);

-- =====================================================================
-- change_reports — output of agents.change_detector
-- =====================================================================

CREATE TABLE IF NOT EXISTS change_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL,
    severity TEXT NOT NULL,                        -- new|unchanged|metadata|improved|reduced|ended
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL,
    today_id TEXT,
    yesterday_id TEXT,
    detected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_change_reports_provider_id
    ON change_reports (provider_id);
CREATE INDEX IF NOT EXISTS idx_change_reports_detected_at
    ON change_reports (detected_at DESC);

-- =====================================================================
-- verify_queue — low-confidence records awaiting human review
-- =====================================================================

CREATE TABLE IF NOT EXISTS verify_queue (
    record_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    parse_confidence TEXT NOT NULL,
    reason TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    record_payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending|confirmed|rejected
    resolved_at TEXT,
    resolved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_verify_queue_status
    ON verify_queue (status);
