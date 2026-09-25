"use client";

import { Button } from "@/components/ui/button";

/** Checkbox popover for discover/force flags + the start-run action. */
export function RefreshOptionsPopover({
  discover,
  onDiscoverChange,
  force,
  onForceChange,
  starting,
  onStart,
}: {
  discover: boolean;
  onDiscoverChange: (value: boolean) => void;
  force: boolean;
  onForceChange: (value: boolean) => void;
  starting: boolean;
  onStart: () => void;
}) {
  return (
    <div className="absolute right-0 top-full z-40 mt-2 w-64 rounded-lg border border-border bg-bg-surface p-3 shadow-xl">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
        Refresh options
      </p>
      <label className="flex items-center gap-2 py-1 text-xs text-fg">
        <input
          type="checkbox"
          checked={discover}
          onChange={(e) => onDiscoverChange(e.target.checked)}
          className="h-3.5 w-3.5 rounded border-border-strong"
        />
        Also discover new providers
      </label>
      <label className="flex items-center gap-2 py-1 text-xs text-fg">
        <input
          type="checkbox"
          checked={force}
          onChange={(e) => onForceChange(e.target.checked)}
          className="h-3.5 w-3.5 rounded border-border-strong"
        />
        Force re-extract
      </label>
      <Button type="button" size="sm" className="mt-2 w-full" onClick={onStart} disabled={starting}>
        {starting ? "Starting…" : "Start refresh"}
      </Button>
    </div>
  );
}
