"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import {
  TIERS,
  TIER_LABELS,
  CATEGORIES,
  CATEGORY_LABELS,
  OFFER_TYPES,
  type Tier,
  type ParseConfidence,
} from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const CONFIDENCE_LEVELS: ParseConfidence[] = ["high", "medium", "low"];

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
      {children}
    </h3>
  );
}

export function Sidebar({
  currentTier,
  tierCounts,
}: {
  currentTier: Tier;
  tierCounts: Record<Tier, number>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedCategories = useMemo(
    () => new Set(searchParams.getAll("category")),
    [searchParams]
  );
  const selectedOfferTypes = useMemo(
    () => new Set(searchParams.getAll("offer_type")),
    [searchParams]
  );
  const region = searchParams.get("region") ?? "any";
  const minConfidence = (searchParams.get("min_confidence") ?? "medium") as ParseConfidence;

  const update = useCallback(
    (mutator: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutator(params);
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  const setTier = (t: Tier) => update((p) => p.set("tier", t));
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
  const setRegion = (v: string) =>
    update((p) => {
      if (v === "any") p.delete("region");
      else p.set("region", v);
    });
  const setConfidence = (c: ParseConfidence) =>
    update((p) => p.set("min_confidence", c));
  const reset = () => router.push("/");

  return (
    <aside
      aria-label="Filters"
      className="sticky top-[73px] flex h-[calc(100dvh-73px)] w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-border bg-bg-base px-5 py-6"
    >
      {/* Tier */}
      <section>
        <SectionTitle>Project tier</SectionTitle>
        <div role="radiogroup" aria-label="Project tier" className="flex flex-col gap-1">
          {TIERS.map((t) => {
            const active = t === currentTier;
            return (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setTier(t)}
                className={cn(
                  "group flex items-center justify-between rounded-md px-3 py-1.5 text-sm transition-colors",
                  "hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                  active && "bg-bg-tile text-accent"
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      active ? "bg-accent" : "bg-border-strong"
                    )}
                  />
                  {TIER_LABELS[t]}
                </span>
                <span
                  className={cn(
                    "font-mono text-xs",
                    active ? "text-accent" : "text-fg-subtle"
                  )}
                >
                  {tierCounts[t] ?? 0}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Category */}
      <section>
        <SectionTitle>Category</SectionTitle>
        <div className="flex flex-col gap-1.5">
          {CATEGORIES.map((c) => {
            const checked = selectedCategories.has(c);
            return (
              <label
                key={c}
                className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm text-fg-muted hover:text-fg"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleArrayParam("category", c)}
                  className="h-3.5 w-3.5 rounded border-border-strong text-accent focus:ring-accent"
                />
                {CATEGORY_LABELS[c]}
              </label>
            );
          })}
        </div>
      </section>

      {/* Offer type */}
      <section>
        <SectionTitle>Offer type</SectionTitle>
        <div className="flex flex-col gap-1.5">
          {OFFER_TYPES.map((o) => {
            const checked = selectedOfferTypes.has(o);
            return (
              <label
                key={o}
                className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 font-mono text-xs text-fg-muted hover:text-fg"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleArrayParam("offer_type", o)}
                  className="h-3.5 w-3.5 rounded border-border-strong text-accent focus:ring-accent"
                />
                {o}
              </label>
            );
          })}
        </div>
      </section>

      {/* Region */}
      <section>
        <SectionTitle>Region</SectionTitle>
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="w-full rounded-md border border-border bg-bg-surface px-2 py-1.5 text-sm text-fg focus:outline-none focus:ring-2 focus:ring-accent"
          aria-label="Region"
        >
          <option value="any">any</option>
          <option value="india">India only</option>
          <option value="india-accessible">India-accessible</option>
        </select>
      </section>

      {/* Min parse confidence */}
      <section>
        <SectionTitle>Min parse confidence</SectionTitle>
        <div role="radiogroup" aria-label="Minimum parse confidence" className="grid grid-cols-3 gap-1">
          {CONFIDENCE_LEVELS.map((c) => {
            const active = c === minConfidence;
            return (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setConfidence(c)}
                className={cn(
                  "rounded-md border px-2 py-1.5 text-xs font-medium capitalize transition-colors",
                  active
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile"
                )}
              >
                {c}
              </button>
            );
          })}
        </div>
      </section>

      <div className="mt-auto pt-2">
        <Button variant="outline" className="w-full" onClick={reset}>
          Reset filters
        </Button>
      </div>
    </aside>
  );
}
