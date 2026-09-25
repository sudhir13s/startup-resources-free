import { ResourceCard } from "@/components/ResourceCard";
import { FundCard } from "@/components/FundCard";
import type { ProviderRecord } from "@/lib/types";

/** Renders a grid of provider records, switching each cell's card shape
 * on `card_variant` (backend-derived). Mixed lists (e.g. Compare) render
 * correctly because the discrimination is per-record, not per-grid. */
export function ProviderGrid({ items }: { items: ProviderRecord[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <p className="text-sm text-fg-muted">No free-tier resources match these filters.</p>
        <p className="mt-2 text-xs text-fg-subtle">
          Try widening the project tier, lowering parse confidence, or opening an issue on{" "}
          <a
            href="https://github.com/sudhir13s/startup-resources-free/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            GitHub
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {items.map((p) =>
        p.card_variant === "funds" ? (
          <FundCard key={p.provider_id} provider={p} />
        ) : (
          <ResourceCard key={p.provider_id} provider={p} />
        )
      )}
    </div>
  );
}

export function ProviderGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading resources"
      className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton h-72 rounded-xl border border-border" />
      ))}
    </div>
  );
}
