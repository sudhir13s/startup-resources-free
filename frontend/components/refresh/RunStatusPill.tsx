import { relativeTime } from "@/lib/utils";
import type { RunReport } from "@/lib/types";
import { cn } from "@/lib/utils";

const STALE_AFTER_DAYS = 14;

function daysSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 86_400_000;
}

/** Idle-state freshness pill: "Updated <relative time>", amber/red when stale or failed. */
export function RunStatusPill({
  lastRun,
  dataSyncedAt,
}: {
  lastRun: RunReport | null;
  dataSyncedAt: string | null;
}) {
  const anchor = lastRun?.finished_at ?? dataSyncedAt;
  const failed = lastRun?.status === "failed";
  const stale = anchor ? daysSince(anchor) > STALE_AFTER_DAYS : true;

  const tone = failed ? "bg-bad" : stale ? "bg-warn" : "bg-ok";
  const label = anchor ? `Updated ${relativeTime(anchor)}` : "Never updated";

  return (
    <span
      className={cn(
        "hidden items-center gap-2 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-[11px] text-fg-muted sm:inline-flex",
      )}
      title={failed ? "Last refresh failed" : label}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", tone)} aria-hidden="true" />
      {failed ? "Last refresh failed" : label}
    </span>
  );
}
