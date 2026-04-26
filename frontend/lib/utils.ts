import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type Tier = "hobby" | "personal" | "startup-mvp" | "startup";

export const TIERS: Tier[] = ["hobby", "personal", "startup-mvp", "startup"];

export const TIER_LABELS: Record<Tier, string> = {
  hobby: "Hobby",
  personal: "Personal",
  "startup-mvp": "Startup MVP",
  startup: "Startup",
};

export const TIER_DESCRIPTIONS: Record<Tier, string> = {
  hobby: "Weekend tinkering, learning, throwaway demos",
  personal: "Small personal site or tool, single user, always-on",
  "startup-mvp": "Pre-revenue prototype, 10–1000 users, easy upgrade path",
  startup: "Paying users, production reliability, free tier as dev/sandbox",
};

export const DEFAULT_TIER: Tier = "startup-mvp";

export type GeoPriority =
  | "india-native"
  | "accessible-from-india"
  | "global-other"
  | "us-only"
  | "eu-only"
  | "other-region";

export type ParseConfidence = "high" | "medium" | "low";

export type Provider = {
  id: string;
  name: string;
  category: string;
  headline: string;
  free_tier_summary: string;
  use_case_tiers: Tier[];
  india_accessible: boolean;
  geo_priority: GeoPriority;
  source_url: string;
  parse_confidence: ParseConfidence;
  last_verified_at: string;
  notes?: string | null;
};

export type ProvidersResponse = {
  total: number;
  matched: number;
  items: Provider[];
};

export function isTier(value: string | undefined): value is Tier {
  return value !== undefined && (TIERS as string[]).includes(value);
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
