"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import { cn } from "@/lib/utils";
import { FUND_KINDS, type FundKind } from "@/lib/fund-kinds";

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
      {children}
    </h3>
  );
}

export function FundsSidebar({
  kindCounts,
}: {
  /** map from kind-key → count of records in that kind (after region filter). */
  kindCounts: Record<FundKind, number>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedKinds = useMemo(
    () => new Set(searchParams.getAll("fund_kind")),
    [searchParams],
  );
  const region = searchParams.get("region") ?? "any";

  const update = useCallback(
    (mutator: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutator(params);
      router.push(`/funds?${params.toString()}`);
    },
    [router, searchParams],
  );

  const toggleKind = (key: string) =>
    update((p) => {
      const all = p.getAll("fund_kind");
      p.delete("fund_kind");
      if (all.includes(key)) {
        all.filter((v) => v !== key).forEach((v) => p.append("fund_kind", v));
      } else {
        [...all, key].forEach((v) => p.append("fund_kind", v));
      }
    });

  const setRegion = (v: string) =>
    update((p) => {
      if (v === "any") p.delete("region");
      else p.set("region", v);
    });

  const reset = () => router.push("/funds");

  return (
    <aside
      aria-label="Funds filters"
      className="sticky top-[73px] flex h-[calc(100dvh-73px)] w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-border bg-bg-base px-5 py-6"
    >
      {/* Kind */}
      <section>
        <SectionTitle>Kind</SectionTitle>
        <div className="flex flex-col gap-1.5">
          {FUND_KINDS.map((k) => {
            const checked = selectedKinds.has(k.key);
            const count = kindCounts[k.key] ?? 0;
            return (
              <label
                key={k.key}
                className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-1 text-sm text-fg-muted hover:text-fg"
              >
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleKind(k.key)}
                    className="h-3.5 w-3.5 rounded border-border-strong text-warn focus:ring-warn"
                    aria-label={k.label}
                  />
                  {k.label}
                </span>
                <span
                  className={cn(
                    "font-mono text-xs",
                    checked ? "text-warn" : "text-fg-subtle",
                  )}
                >
                  {count}
                </span>
              </label>
            );
          })}
        </div>
      </section>

      {/* Region */}
      <section>
        <SectionTitle>Region</SectionTitle>
        <div role="radiogroup" aria-label="Region" className="flex flex-col gap-1">
          {[
            { v: "any", label: "All regions" },
            { v: "india", label: "India-accessible" },
          ].map((r) => {
            const active = r.v === region;
            return (
              <button
                key={r.v}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setRegion(r.v)}
                className={cn(
                  "flex items-center justify-between rounded-md px-3 py-1.5 text-sm transition-colors",
                  "hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                  active && "bg-bg-tile text-accent",
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      active ? "bg-accent" : "bg-border-strong",
                    )}
                  />
                  {r.label}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <button
        type="button"
        onClick={reset}
        className="mt-auto rounded-md border border-border bg-bg-tile px-3 py-1.5 text-xs font-medium text-fg-muted hover:bg-bg-surface hover:text-fg"
      >
        Reset filters
      </button>
    </aside>
  );
}
