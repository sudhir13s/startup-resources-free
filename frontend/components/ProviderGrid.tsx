import { ProviderCard } from "@/components/ProviderCard";
import type { Provider } from "@/lib/utils";

export function ProviderGrid({ items }: { items: Provider[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-bg-subtle bg-bg-surface/40 p-12 text-center">
        <p className="text-sm text-white/70">
          No free-tier resources match this filter yet.
        </p>
        <p className="mt-2 text-xs text-white/50">
          Open an issue on{" "}
          <a
            href="https://github.com/sudhir13s/startup-resources-free/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            GitHub
          </a>{" "}
          to suggest one.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((p) => (
        <ProviderCard key={p.id} provider={p} />
      ))}
    </div>
  );
}

export function ProviderGridSkeleton({ count = 9 }: { count?: number }) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading resources"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="skeleton h-56 rounded-lg border border-bg-subtle"
        />
      ))}
    </div>
  );
}
