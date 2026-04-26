"use client";

import Link from "next/link";
import { Search, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";

export function TopBar({
  lastUpdated = "2h ago",
}: {
  lastUpdated?: string;
}) {
  return (
    <header
      role="banner"
      className="sticky top-0 z-30 flex flex-wrap items-center gap-3 border-b border-border bg-bg-base/90 px-4 py-3 backdrop-blur sm:flex-nowrap sm:gap-4 sm:px-6"
    >
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent text-base font-bold text-accent-fg">
          R
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight text-fg">
            ResourceOS
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">
            v0.1 · catalog
          </span>
        </div>
      </div>

      <nav aria-label="Primary" className="flex items-center gap-1 shrink-0">
        <Link
          href="/"
          className="rounded-md border border-border-strong bg-bg-surface px-3 py-1.5 text-xs font-medium text-fg"
        >
          Catalog
        </Link>
        <span
          className="cursor-not-allowed rounded-md px-3 py-1.5 text-xs text-fg-subtle"
          title="Coming soon"
        >
          Media Benchmark
        </span>
        <span
          className="cursor-not-allowed rounded-md px-3 py-1.5 text-xs text-fg-subtle"
          title="Coming soon"
        >
          Settings
        </span>
      </nav>

      <div className="order-last flex w-full items-center sm:order-none sm:flex-1 sm:max-w-md">
        <label htmlFor="search" className="sr-only">
          Search resources
        </label>
        <div className="relative w-full">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <input
            id="search"
            type="text"
            placeholder='Try "free postgres 10gb" or "AI inference for India"'
            disabled
            aria-disabled="true"
            className="h-9 w-full rounded-md border border-border bg-bg-surface pl-9 pr-12 text-xs text-fg placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-70"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle sm:inline">
            ⌘K
          </kbd>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-2 shrink-0">
        <span className="hidden items-center gap-2 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-[11px] text-fg-muted sm:inline-flex">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true" />
          updated {lastUpdated}
        </span>
        <Button size="sm" className="h-9" disabled title="Coming soon">
          <RefreshCw className="h-3.5 w-3.5" />
          Run now
        </Button>
        <ThemeToggle />
      </div>
    </header>
  );
}
