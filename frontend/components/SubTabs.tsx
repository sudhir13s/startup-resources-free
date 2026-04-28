"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

type Tab = {
  key: string;
  label: string;
  href: string;
  soon: boolean;
};

const TABS: readonly Tab[] = [
  { key: "catalog", label: "Catalog", href: "/", soon: false },
  { key: "grants", label: "Grants & Credits", href: "/grants", soon: false },
  { key: "compare", label: "Compare", href: "/compare", soon: false },
] as const;

export function SubTabs({ matchedCount }: { matchedCount?: number }) {
  const pathname = usePathname();

  return (
    <div
      role="tablist"
      aria-label="Catalog views"
      className="flex items-center gap-1 border-b border-border"
    >
      {TABS.map((t) => {
        const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
        const className = cn(
          "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm transition-colors",
          active ? "border-accent text-fg" : "border-transparent text-fg-subtle",
          t.soon && "cursor-not-allowed"
        );

        const badge = (() => {
          if (active && t.key === "catalog" && typeof matchedCount === "number") {
            return (
              <span className="rounded bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {matchedCount}
              </span>
            );
          }
          if (t.soon) {
            return (
              <span className="rounded bg-bg-tile px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
                Soon
              </span>
            );
          }
          return null;
        })();

        if (t.soon) {
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={false}
              aria-disabled
              disabled
              title="Coming soon"
              className={className}
            >
              {t.label}
              {badge}
            </button>
          );
        }

        return (
          <Link
            key={t.key}
            href={t.href}
            role="tab"
            aria-selected={active}
            aria-current={active ? "page" : undefined}
            className={className}
          >
            {t.label}
            {badge}
          </Link>
        );
      })}
    </div>
  );
}
