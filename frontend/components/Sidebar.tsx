"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { TierFilter } from "@/components/catalog/filters/TierFilter";
import { CategoryFilter } from "@/components/catalog/filters/CategoryFilter";
import { OfferTypeFilter } from "@/components/catalog/filters/OfferTypeFilter";
import { RegionFilter } from "@/components/catalog/filters/RegionFilter";
import { ConfidenceFilter } from "@/components/catalog/filters/ConfidenceFilter";
import type { CardVariant, Facets, GeoPriority, OfferType, ParseConfidence, UseCaseTier } from "@/lib/types";
import { DEFAULT_VISIBLE_GEO, EXPANDABLE_GEO, FUND_CATEGORIES, RESOURCE_CATEGORIES } from "@/lib/catalog/labels";

/**
 * Shared filter sidebar for /resources and /funds. Variant-aware: shows
 * only the categories that apply to the current view, and writes URL
 * updates on the CURRENT pathname (router.replace — never a redirect
 * through `/`, so filtering never triggers an extra navigation hop).
 */
export function Sidebar({ variant, facets }: { variant: CardVariant; facets: Facets | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [showAllGeo, setShowAllGeo] = useState(() =>
    EXPANDABLE_GEO.some((g) => searchParams.getAll("geo").includes(g))
  );

  const selectedTiers = useMemo(() => new Set(searchParams.getAll("tier")), [searchParams]);
  const selectedCategories = useMemo(() => new Set(searchParams.getAll("category")), [searchParams]);
  const selectedOfferTypes = useMemo(() => new Set(searchParams.getAll("offer_type")), [searchParams]);
  const selectedGeo = useMemo(() => {
    const fromUrl = new Set(searchParams.getAll("geo"));
    return fromUrl.size > 0 ? fromUrl : new Set<string>(DEFAULT_VISIBLE_GEO);
  }, [searchParams]);
  const minConfidence = (searchParams.get("min_confidence") ?? null) as ParseConfidence | null;

  const update = useCallback(
    (mutator: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutator(params);
      router.replace(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams]
  );

  const toggleArrayParam = (key: string, value: string) =>
    update((p) => {
      const all = p.getAll(key);
      p.delete(key);
      if (all.includes(value)) {
        all.filter((v) => v !== value).forEach((v) => p.append(key, v));
      } else {
        [...all, value].forEach((v) => p.append(key, v));
      }
    });

  const setTier = (t: UseCaseTier) =>
    update((p) => {
      const all = p.getAll("tier");
      p.delete("tier");
      // Radio with a clearable "All": clicking the active tier clears it;
      // clicking another replaces the whole set with just it.
      if (all.length === 1 && all[0] === t) return;
      p.append("tier", t);
    });
  const clearTier = () => update((p) => p.delete("tier"));

  const toggleGeo = (g: GeoPriority) =>
    update((p) => {
      const current = p.getAll("geo");
      const base = current.length > 0 ? current : [...DEFAULT_VISIBLE_GEO];
      p.delete("geo");
      if (base.includes(g)) {
        base.filter((v) => v !== g).forEach((v) => p.append("geo", v));
      } else {
        [...base, g].forEach((v) => p.append("geo", v));
      }
    });

  const setShowExpandedGeo = (show: boolean) => {
    setShowAllGeo(show);
    update((p) => {
      const current = p.getAll("geo");
      const base = current.length > 0 ? current : [...DEFAULT_VISIBLE_GEO];
      p.delete("geo");
      if (show) {
        [...new Set([...base, ...EXPANDABLE_GEO])].forEach((v) => p.append("geo", v));
      } else {
        base.filter((v) => !EXPANDABLE_GEO.includes(v as GeoPriority)).forEach((v) => p.append("geo", v));
      }
    });
  };

  const setConfidence = (c: ParseConfidence | null) =>
    update((p) => {
      if (c === null) p.delete("min_confidence");
      else p.set("min_confidence", c);
    });

  const reset = () => router.replace(pathname);
  const categories = variant === "resource" ? RESOURCE_CATEGORIES : FUND_CATEGORIES;

  return (
    <aside
      aria-label="Filters"
      className="sticky top-[73px] flex h-[calc(100dvh-73px)] w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-border bg-bg-base px-5 py-6"
    >
      <TierFilter selected={selectedTiers} facets={facets} onSelect={setTier} onClear={clearTier} />
      <CategoryFilter
        categories={categories}
        selected={selectedCategories}
        facets={facets}
        onToggle={(c) => toggleArrayParam("category", c)}
      />
      <OfferTypeFilter
        selected={selectedOfferTypes}
        facets={facets}
        onToggle={(o: OfferType) => toggleArrayParam("offer_type", o)}
      />
      <RegionFilter
        selected={selectedGeo}
        facets={facets}
        showAll={showAllGeo}
        onToggle={toggleGeo}
        onToggleShowAll={setShowExpandedGeo}
      />
      <ConfidenceFilter value={minConfidence} onSelect={setConfidence} />

      <div className="mt-auto pt-2">
        <Button variant="outline" className="w-full" onClick={reset}>
          Reset filters
        </Button>
      </div>
    </aside>
  );
}
