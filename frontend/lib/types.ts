/**
 * API contract — mirrors the Python domain package (`domain/*.py`).
 * Change both sides together; `api/tests/test_contract.py` checks the enums.
 *
 * Endpoints (FastAPI, base = BACKEND_URL):
 *   GET  /api/health                         → { status, service_name, version, data_synced_at }
 *   GET  /api/providers?variant=&tier=&category=&offer_type=&geo=&min_confidence=&q=
 *        (tier / category / offer_type / geo are repeatable)  → ProvidersResponse
 *   GET  /api/providers/{provider_id}        → ProviderDetailResponse   (404 if unknown)
 *   GET  /api/changes?limit=&since=YYYY-MM-DD → ChangesResponse
 *   GET  /api/runs?limit=                    → RunReport[]
 *   GET  /api/runs/{run_id}                  → RunReport
 *   GET  /api/refresh/status                 → RefreshStatus
 *   POST /api/refresh            [admin]     body RefreshOptions → 202 { run_id } | 409 { detail }
 *   GET  /api/candidates?status=             → Candidate[]
 *   POST /api/candidates/{id}/approve [admin] → 200 Candidate
 *   POST /api/candidates/{id}/reject  [admin] → 200 Candidate
 *   GET  /api/freellm/catalog · /api/freellm/plan?modality=   (unchanged)
 *
 * [admin] = header `X-ResourceOS-Passphrase: <RESOURCEOS_PASSPHRASE>`. The browser never sees the token:
 * Next.js route handlers under `app/api/admin/*` add it server-side after the
 * passphrase login sets an httpOnly session cookie.
 * Errors: `{ detail: string }` with 400 / 401 / 404 / 409 / 422.
 */

export type ResourceCategory =
  | "cloud" | "gpu" | "ai-api" | "database" | "storage" | "auth"
  | "observability" | "domain" | "dev-tools" | "oss" | "learning";
export type FundCategory = "startup-credit" | "grant" | "accelerator" | "perk";
export type Category = ResourceCategory | FundCategory;

export type OfferType =
  | "free-tier" | "free-credits" | "free-trial" | "free-quota" | "grant" | "perk" | "oss";
export type PricingLayer = "always-free" | "12-month" | "trial" | "credit" | "quota";
export type LimitPeriod = "minute" | "hour" | "day" | "month" | "year" | "once" | "total";
export type AccessMethod =
  | "api-key" | "oauth" | "signup" | "email-verify" | "github-auth"
  | "manual-apply" | "invite-only" | "contact-sales" | "unknown";
export type GeoPriority =
  | "india-native" | "accessible-from-india" | "global-other"
  | "us-only" | "eu-only" | "other-region";
export type UseCaseTier = "hobby" | "personal" | "startup-mvp" | "pre-seed" | "seed" | "series-a";
export type ParseConfidence = "high" | "medium" | "low";
export type SourceMethod = "manual" | "llm" | "api";
export type RecordStatus = "active" | "reduced" | "ended" | "unknown";
export type CardVariant = "resource" | "funds";

export interface Limit {
  label: string;
  value: number | string | boolean;
  unit: string | null;
  period: LimitPeriod | null;
  note: string | null;
}

export interface Service {
  name: string;
  category: ResourceCategory;
  service_type: string | null;
  pricing_layer: PricingLayer;
  summary: string;
  limits: Limit[];
  notes: string | null;
}

export interface Credit {
  label: string;
  amount: number | null;
  currency: string | null;
  duration_days: number | null;
  conditions: string | null;
}

export interface Link {
  label: string;
  url: string;
}

export interface Eligibility {
  regions: string[];
  user_types: string[];
  company_age_max_years: number | null;
  funding_max_usd: number | null;
}

export interface ProviderRecord {
  provider_id: string;
  name: string;
  vendor: string;
  category: Category;
  source_urls: string[];
  offer_type: OfferType;
  headline: string;
  highlights: string[];
  services: Service[];
  credits: Credit[];
  quota_summary: string;
  duration_summary: string;
  region_summary: string;
  eligibility_summary: string;
  eligibility: Eligibility;
  access_method: AccessMethod;
  claim_steps: string[];
  restrictions: string[];
  gotchas: string[];
  after_free_period: string | null;
  links: Link[];
  geo_priority: GeoPriority;
  always_on: boolean | null;
  use_case_tiers: UseCaseTier[];
  tier_fit_rationale: string | null;
  parse_confidence: ParseConfidence;
  source_method: SourceMethod;
  last_verified_at: string | null; // YYYY-MM-DD
  scraped_at: string;              // ISO datetime
  expiry_date: string | null;
  status: RecordStatus;
  notes: string | null;
  // derived by the API
  categories: Category[];
  card_variant: CardVariant;
  india_accessible: boolean;
}

export interface Facets {
  tiers: Record<string, number>;
  categories: Record<string, number>;
  offer_types: Record<string, number>;
  geo: Record<string, number>;
}

export interface ProvidersResponse {
  total: number;   // records in the requested variant (or all)
  matched: number;
  items: ProviderRecord[];
  facets: Facets;
}

export interface VersionSummary {
  version: number;
  source: string;
  run_id: string | null;
  created_at: string;
}

export interface ProviderDetailResponse {
  record: ProviderRecord;
  history: VersionSummary[];
  related: Pick<ProviderRecord, "provider_id" | "name" | "category" | "offer_type">[]; // same vendor
}

export type ChangeSeverity = "new" | "improved" | "reduced" | "ended" | "metadata";

export interface FieldChange {
  provider_id: string;
  provider_name: string;
  category: string;
  field: string;
  old_value: unknown;
  new_value: unknown;
  severity: ChangeSeverity;
  detected_at: string;
  run_id: string | null;
}

export interface ChangesResponse {
  total: number;
  items: FieldChange[];
}

export type RunStatus = "running" | "succeeded" | "partial" | "failed";
export type OutcomeStatus =
  | "unchanged" | "updated" | "new" | "queued-verify" | "skipped" | "failed";

export interface RefreshOptions {
  provider_ids: string[] | null;
  discover: boolean;
  force: boolean;
  max_llm_calls: number;
}

export interface ProviderOutcome {
  provider_id: string;
  status: OutcomeStatus;
  message: string;
  source_url: string | null;
  llm_provider: string | null;
  changes: number;
  duration_ms: number;
}

export interface RunReport {
  run_id: string;
  trigger: "button" | "cli" | "test";
  options: RefreshOptions;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  outcomes: ProviderOutcome[];
  candidates_found: number;
  llm_calls: number;
  search_calls: number;
  data_pushed: boolean;
  errors: string[];
}

export interface RefreshStatus {
  active: RunReport | null;
  last: RunReport | null;
  data_synced_at: string | null; // last successful push to / pull from the data branch
}

export type CandidateStatus = "pending" | "approved" | "rejected" | "imported";

export interface Candidate {
  candidate_id: string;
  url: string;
  domain: string;
  title: string;
  snippet: string;
  category_guess: string | null;
  reason: string;
  score: number;
  found_via: string;
  status: CandidateStatus;
  created_at: string;
}
