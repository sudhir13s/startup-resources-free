import { cn } from "@/lib/utils";

const TABS = [
  { key: "catalog", label: "Catalog", active: true, soon: false },
  { key: "compare", label: "Compare", active: false, soon: true },
  { key: "changes", label: "Changes", active: false, soon: true },
  { key: "verify", label: "Verify", active: false, soon: true },
] as const;

export function SubTabs({ matchedCount }: { matchedCount: number }) {
  return (
    <div
      role="tablist"
      aria-label="Catalog views"
      className="flex items-center gap-1 border-b border-border"
    >
      {TABS.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          aria-selected={t.active}
          aria-disabled={t.soon}
          disabled={t.soon}
          title={t.soon ? "Coming soon" : undefined}
          className={cn(
            "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors",
            t.active
              ? "border-accent text-fg"
              : "border-transparent text-fg-subtle",
            t.soon && "cursor-not-allowed"
          )}
        >
          {t.label}
          {t.active ? (
            <span className="rounded bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
              {matchedCount}
            </span>
          ) : (
            <span className="rounded bg-bg-tile px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
              Soon
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
