/**
 * Shared parsing of the catalog filter search params. Used by both
 * /resources and /funds server components, and mirrored client-side
 * by the Sidebar for building the next URL.
 */

import type { CardVariant, GeoPriority, OfferType, ParseConfidence, UseCaseTier } from "@/lib/types";
import { ALL_GEO, CONFIDENCE_LEVELS, OFFER_TYPES, TIERS } from "@/lib/catalog/labels";

export type SearchParams = Record<string, string | string[] | undefined>;

export function getAll(searchParams: SearchParams | undefined, key: string): string[] {
  if (!searchParams) return [];
  const v = searchParams[key];
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

export function getOne(searchParams: SearchParams | undefined, key: string): string | undefined {
  if (!searchParams) return undefined;
  const v = searchParams[key];
  return Array.isArray(v) ? v[0] : v;
}

export interface CatalogFilters {
  tiers: UseCaseTier[];
  categories: string[];
  offerTypes: OfferType[];
  geo: GeoPriority[];
  minConfidence: ParseConfidence | null;
  query: string | null;
}

/** Parse + validate every filter param. Invalid/unknown values are
 * dropped rather than causing a fetch to fail — the backend applies
 * the same validation for 400/422 detection. */
export function parseCatalogFilters(searchParams: SearchParams | undefined): CatalogFilters {
  const tiers = getAll(searchParams, "tier").filter((t): t is UseCaseTier =>
    (TIERS as string[]).includes(t)
  );
  const categories = getAll(searchParams, "category");
  const offerTypes = getAll(searchParams, "offer_type").filter((o): o is OfferType =>
    (OFFER_TYPES as string[]).includes(o)
  );
  const geo = getAll(searchParams, "geo").filter((g): g is GeoPriority =>
    (ALL_GEO as string[]).includes(g)
  );
  const rawConfidence = getOne(searchParams, "min_confidence");
  const minConfidence = (CONFIDENCE_LEVELS as string[]).includes(rawConfidence ?? "")
    ? (rawConfidence as ParseConfidence)
    : null;
  const rawQuery = getOne(searchParams, "q");
  const query = rawQuery && rawQuery.trim().length > 0 ? rawQuery.trim() : null;

  return { tiers, categories, offerTypes, geo, minConfidence, query };
}

/** Build the backend query string for `/api/providers`. */
export function buildProvidersQuery(
  variant: CardVariant,
  filters: CatalogFilters
): Record<string, string | string[]> {
  const query: Record<string, string | string[]> = { variant };
  if (filters.tiers.length > 0) query.tier = filters.tiers;
  if (filters.categories.length > 0) query.category = filters.categories;
  if (filters.offerTypes.length > 0) query.offer_type = filters.offerTypes;
  if (filters.geo.length > 0) query.geo = filters.geo;
  if (filters.minConfidence) query.min_confidence = filters.minConfidence;
  if (filters.query) query.q = filters.query;
  return query;
}
