"use client";

import { Search, RefreshCw } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { CronStatus } from "@/lib/utils";

function freshnessText(status: CronStatus | null | undefined): string {
  if (!status) return "—";
  const ages = [status.refresh_age_days, status.discovery_age_days].filter(
    (a): a is number => typeof a === "number",
  );
  if (ages.length === 0) return "never run";
  const youngest = Math.min(...ages);
  if (youngest === 0) return "today";
  if (youngest === 1) return "1 day ago";
  return `${youngest} days ago`;
}

export function TopBar({
  lastUpdated = "2h ago",
  cronStatus,
}: {
  lastUpdated?: string;
  cronStatus?: CronStatus | null;
}) {
  const stale = cronStatus?.is_stale ?? true;
  const freshness = cronStatus ? freshnessText(cronStatus) : lastUpdated;
  const runUrl =
    cronStatus?.workflow_url_discovery ??
    "https://github.com/sudhir13s/startup-resources-free/actions/workflows/weekly-discovery.yml";
  const tooltip = stale
    ? "Trigger the weekly-discovery workflow on GitHub Actions (opens in a new tab)"
    : `Last run ${freshness} — cron is up-to-date. Click anyway to force-run.`;
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

      {/* Top-level nav lives in SubTabs (Resources / Compare / Funds &
          Credits). The legacy "Catalog / Free-LLM Chain / Media
          Benchmark / Settings" pills are removed per the 2026-04-28
          roundtable — Free-LLM Chain + Media Benchmark were demoted to
          utility URLs only (no nav entry), and Settings was always a
          placeholder. */}
      <div className="order-last flex w-full items-center sm:order-none sm:flex-1 sm:max-w-md">
        <button
          type="button"
          onClick={() =>
            window.dispatchEvent(new CustomEvent("open-command-palette"))
          }
          aria-label='Open search ("⌘K")'
          aria-haspopup="dialog"
          className="relative flex h-9 w-full items-center rounded-md border border-border bg-bg-surface pl-9 pr-12 text-left text-xs text-fg-subtle hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <span className="truncate">
            Try &quot;free postgres 10gb&quot; or &quot;AI inference for India&quot;
          </span>
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle sm:inline">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="ml-auto flex items-center gap-2 shrink-0">
        <span className="hidden items-center gap-2 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-[11px] text-fg-muted sm:inline-flex">
          <span
            className={
              "h-1.5 w-1.5 rounded-full " + (stale ? "bg-warn" : "bg-ok")
            }
            aria-hidden="true"
          />
          updated {freshness}
        </span>
        {/* Run now: ALWAYS clickable (user override 2026-04-28).
            Opens GitHub Actions workflow_dispatch UI in a new tab — uses
            GitHub's own auth, no PAT round-trip from the dashboard.
            Visual emphasis stronger when cron is stale; muted-but-clickable
            when fresh so the user can still force-run anytime. */}
        <a
          href={runUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={tooltip}
          className={
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors " +
            (stale
              ? "border-accent/40 bg-accent/10 text-accent hover:bg-accent/15"
              : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile hover:text-fg")
          }
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Run now
        </a>
        <ThemeToggle />
      </div>
    </header>
  );
}
