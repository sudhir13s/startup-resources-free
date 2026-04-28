import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type Tier =
  | "hobby"
  | "personal"
  | "startup-mvp"
  | "pre-seed"
  | "seed"
  | "series-a";

export const TIERS: Tier[] = [
  "hobby",
  "personal",
  "startup-mvp",
  "pre-seed",
  "seed",
  "series-a",
];

export const TIER_LABELS: Record<Tier, string> = {
  hobby: "Hobby",
  personal: "Personal",
  "startup-mvp": "Startup MVP",
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
};

export const TIER_DESCRIPTIONS: Record<Tier, string> = {
  hobby: "Weekend tinkering, learning, throwaway demos",
  personal: "Small personal site or tool, single user, always-on",
  "startup-mvp": "Pre-revenue prototype, 10–1000 users",
  "pre-seed": "Bootstrapped or friends-and-family-funded, early traction",
  seed: "Post-seed round, $0.5–5M raised",
  "series-a": "Post-Series A, paying users + production scale",
};

export const DEFAULT_TIER: Tier = "personal";

export type GeoPriority =
  | "india-native"
  | "accessible-from-india"
  | "global-other"
  | "us-only"
  | "eu-only"
  | "other-region";

export type ParseConfidence = "high" | "medium" | "low";

export type OfferType =
  | "always-free"
  | "free-tier"
  | "free-credits"
  | "free-trial"
  | "free-quota"
  | "grant"
  | "perk"
  | "oss";

export const OFFER_TYPES: OfferType[] = [
  "always-free",
  "free-tier",
  "free-credits",
  "free-trial",
  "free-quota",
  "grant",
  "perk",
  "oss",
];

export const CATEGORIES = [
  "cloud",
  "gpu",
  "ai-api",
  "databases",
  "storage",
  "auth",
  "observability",
  "domains",
  "startup-credits",
  "grants",
  "accelerators",
  "perks",
  "oss",
  "learning",
  "hosting",
] as const;

export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_LABELS: Record<string, string> = {
  cloud: "Cloud",
  gpu: "GPU",
  "ai-api": "AI APIs",
  databases: "Databases",
  storage: "Storage",
  auth: "Auth",
  observability: "Observability",
  domains: "Domains",
  "startup-credits": "Startup Credits",
  grants: "Grants",
  accelerators: "Accelerators",
  perks: "Perks",
  oss: "OSS",
  learning: "Learning",
  hosting: "Hosting",
};

/** Routes a provider to /resources vs /funds and to ResourceCard vs
 * FundCard. Sprint #5 / CRITICAL #5.
 *
 * Backend computes this from `category` and emits it on every record.
 * Mirror of `schema.records.category_card_variant`.
 */
export type CardVariant = "resource" | "funds";

export type Provider = {
  id: string;
  name: string;
  category: string;
  card_variant: CardVariant;
  headline: string;
  free_tier_summary: string;
  quota_summary: string;
  duration_summary: string;
  region_summary: string;
  offer_type: OfferType;
  eligibility_summary: string;
  use_case_tiers: Tier[];
  india_accessible: boolean;
  geo_priority: GeoPriority;
  source_url: string;
  parse_confidence: ParseConfidence;
  last_verified_at: string;
  notes?: string | null;
  // Extended detail fields — backend may omit any of these on older
  // snapshots. Frontend renders them only when present.
  limits?: Record<string, unknown> | null;
  restrictions?: string | null;
  access_method?: string | null;
  subcategory?: string | null;
  tier_fit_rationale?: string | null;
  credit_amount?: number | null;
  credit_duration_days?: number | null;
  currency?: string | null;
  sub_offerings?: SubOffering[] | null;
  always_on?: boolean | null;
};

/** Multi-service breakdown — AWS Free Tier carries 3 sub-offerings
 * (Always Free / 12-Month Free / Trials), each with its own headline +
 * limits dict. Single-service providers have null. */
export type SubOffering = {
  service_name: string;
  headline: string;
  limits: Record<string, unknown>;
};

/** Categories that route to the /funds view. Both canonical singular
 * AND legacy plural slugs included so it works regardless of ingest. */
const FUND_CATEGORIES: ReadonlySet<string> = new Set([
  "grant",
  "grants",
  "startup-credit",
  "startup-credits",
  "accelerator",
  "accelerators",
  "perk",
  "perks",
]);

/** Frontend-side fallback when `card_variant` is missing on the wire
 * (e.g. older snapshots). Mirrors the Python helper in
 * `schema.records.category_card_variant`. */
export function categoryCardVariant(category: string): CardVariant {
  return FUND_CATEGORIES.has(category) ? "funds" : "resource";
}

/** Get the variant from a provider, falling back to category mapping
 * if the backend didn't emit one (defensive — backend always should). */
export function providerCardVariant(provider: Provider): CardVariant {
  return provider.card_variant ?? categoryCardVariant(provider.category);
}

export type ProvidersResponse = {
  total: number;
  matched: number;
  items: Provider[];
  tier_counts: { tier: Tier; count: number }[];
  category_counts: { category: string; count: number }[];
};

export type ChangeSeverity =
  | "new"
  | "improved"
  | "reduced"
  | "ended"
  | "unchanged";

export type Change = {
  provider_id: string;
  provider_name: string;
  category: string;
  field: string;
  old_value: unknown;
  new_value: unknown;
  severity: ChangeSeverity;
  snapshot_date: string;
  detected_at: string;
};

export type ChangesResponse = {
  total: number;
  items: Change[];
  snapshot_dates: string[];
  latest_snapshot: string | null;
};

// /api/cron-status — drives TopBar "Run now" button + freshness pill.
export type CronStatus = {
  last_refresh: string | null;
  last_discovery: string | null;
  refresh_age_days: number | null;
  discovery_age_days: number | null;
  is_stale: boolean;
  workflow_url_discovery: string;
  workflow_url_refresh: string;
};

export function isTier(value: string | undefined | null): value is Tier {
  return value !== undefined && value !== null && (TIERS as string[]).includes(value);
}

export function isOfferType(value: string): value is OfferType {
  return (OFFER_TYPES as string[]).includes(value);
}

export function relativeTime(isoDate: string): string {
  const then = new Date(isoDate).getTime();
  const now = Date.now();
  const diffSec = Math.round((then - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, "second");
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), "day");
  if (abs < 31536000) return rtf.format(Math.round(diffSec / 2592000), "month");
  return rtf.format(Math.round(diffSec / 31536000), "year");
}

export function tierFitFirst(tiers: Tier[]): Tier | null {
  if (tiers.length === 0) return null;
  return tiers[0];
}

export function tierFitLast(tiers: Tier[]): Tier | null {
  if (tiers.length === 0) return null;
  return tiers[tiers.length - 1];
}

/** Resolve backend base URL.
 *
 * Order of precedence:
 *   1. BACKEND_URL — full URL incl. scheme (manual entry path).
 *   2. BACKEND_HOST — host only, scheme prepended (Render fromService.host).
 *      If the value has no dot (e.g. user entered "startup-resources-api"
 *      thinking it was a service name), auto-append ".onrender.com".
 *   3. http://localhost:8000 — local-dev fallback.
 *
 * Server-only — do NOT call from a Client Component (process.env not
 * available there).
 */
export function resolveBackendUrl(): string {
  const explicit = process.env.BACKEND_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  const rawHost = process.env.BACKEND_HOST?.trim();
  if (rawHost) {
    const cleaned = rawHost
      .replace(/^https?:\/\//, "")
      .replace(/\/+$/, "");
    // Defensive: if user entered a bare Render service name (no TLD),
    // assume it's a `<service>.onrender.com`. Without this, an entry of
    // "startup-resources-api" yields "https://startup-resources-api"
    // which has no DNS resolution and fails every fetch.
    const fullHost = cleaned.includes(".")
      ? cleaned
      : `${cleaned}.onrender.com`;
    return `https://${fullHost}`;
  }

  return "http://localhost:8000";
}
