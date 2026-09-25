/**
 * Single source of truth for every display label the catalog UI renders.
 * Mirrors `domain/taxonomy.py` — keep both sides in sync when a slug is
 * added or renamed there.
 */

import type {
  AccessMethod,
  Category,
  FundCategory,
  GeoPriority,
  LimitPeriod,
  OfferType,
  ParseConfidence,
  PricingLayer,
  ResourceCategory,
  UseCaseTier,
} from "@/lib/types";

export const RESOURCE_CATEGORIES: ResourceCategory[] = [
  "cloud",
  "gpu",
  "ai-api",
  "database",
  "storage",
  "auth",
  "observability",
  "domain",
  "dev-tools",
  "oss",
  "learning",
];

export const FUND_CATEGORIES: FundCategory[] = [
  "startup-credit",
  "grant",
  "accelerator",
  "perk",
];

/** Mirrors `domain.taxonomy.CATEGORY_LABELS`. */
export const CATEGORY_LABELS: Record<Category, string> = {
  cloud: "Cloud & Hosting",
  gpu: "GPU & Notebooks",
  "ai-api": "AI APIs",
  database: "Databases",
  storage: "Storage",
  auth: "Auth",
  observability: "Observability",
  domain: "Domains & Email",
  "dev-tools": "Dev Tools",
  oss: "Open Source",
  learning: "Learning",
  "startup-credit": "Startup Credits",
  grant: "Grants",
  accelerator: "Accelerators",
  perk: "Perks",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category as Category] ?? category;
}

export const OFFER_TYPES: OfferType[] = [
  "free-tier",
  "free-credits",
  "free-trial",
  "free-quota",
  "grant",
  "perk",
  "oss",
];

export const OFFER_TYPE_LABELS: Record<OfferType, string> = {
  "free-tier": "Free tier",
  "free-credits": "Free credits",
  "free-trial": "Free trial",
  "free-quota": "Free quota",
  grant: "Grant",
  perk: "Perk",
  oss: "Open source",
};

export function offerTypeLabel(offerType: string): string {
  return OFFER_TYPE_LABELS[offerType as OfferType] ?? offerType;
}

export const PRICING_LAYER_LABELS: Record<PricingLayer, string> = {
  "always-free": "Always free",
  "12-month": "12 months",
  trial: "Trial",
  credit: "Credit",
  quota: "Quota",
};

export function pricingLayerLabel(layer: string): string {
  return PRICING_LAYER_LABELS[layer as PricingLayer] ?? layer;
}

export const LIMIT_PERIOD_LABELS: Record<LimitPeriod, string> = {
  minute: "per minute",
  hour: "per hour",
  day: "per day",
  month: "per month",
  year: "per year",
  once: "one-time",
  total: "total",
};

export function limitPeriodLabel(period: string | null): string | null {
  if (!period) return null;
  return LIMIT_PERIOD_LABELS[period as LimitPeriod] ?? period;
}

export const ACCESS_METHOD_LABELS: Record<AccessMethod, string> = {
  "api-key": "API key",
  oauth: "OAuth",
  signup: "Sign up",
  "email-verify": "Email verification",
  "github-auth": "GitHub sign-in",
  "manual-apply": "Manual application",
  "invite-only": "Invite only",
  "contact-sales": "Contact sales",
  unknown: "Unknown",
};

export function accessMethodLabel(method: string): string {
  return ACCESS_METHOD_LABELS[method as AccessMethod] ?? method;
}

export const GEO_PRIORITY_LABELS: Record<GeoPriority, string> = {
  "india-native": "India-native",
  "accessible-from-india": "Accessible from India",
  "global-other": "Global",
  "us-only": "US only",
  "eu-only": "EU only",
  "other-region": "Other region",
};

export function geoPriorityLabel(geo: string): string {
  return GEO_PRIORITY_LABELS[geo as GeoPriority] ?? geo;
}

/** Geo values shown by default (India-primary). Everything else needs the
 * sidebar's "Show US / EU / other-region-only" toggle. */
export const DEFAULT_VISIBLE_GEO: GeoPriority[] = [
  "india-native",
  "accessible-from-india",
  "global-other",
];
export const EXPANDABLE_GEO: GeoPriority[] = ["us-only", "eu-only", "other-region"];
export const ALL_GEO: GeoPriority[] = [...DEFAULT_VISIBLE_GEO, ...EXPANDABLE_GEO];

export const TIERS: UseCaseTier[] = [
  "hobby",
  "personal",
  "startup-mvp",
  "pre-seed",
  "seed",
  "series-a",
];

export const TIER_LABELS: Record<UseCaseTier, string> = {
  hobby: "Hobby",
  personal: "Personal",
  "startup-mvp": "Startup MVP",
  "pre-seed": "Pre-seed",
  seed: "Seed",
  "series-a": "Series A",
};

export function tierLabel(tier: string): string {
  return TIER_LABELS[tier as UseCaseTier] ?? tier;
}

export const CONFIDENCE_LEVELS: ParseConfidence[] = ["high", "medium", "low"];

export const CONFIDENCE_LABELS: Record<ParseConfidence, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const CONFIDENCE_DOT_CLASS: Record<ParseConfidence, string> = {
  high: "bg-ok",
  medium: "bg-warn",
  low: "bg-bad",
};
