"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RunStatusPill } from "@/components/refresh/RunStatusPill";
import { RefreshOptionsPopover } from "@/components/refresh/RefreshOptionsPopover";
import { useRefreshStatus } from "@/components/refresh/useRefreshStatus";
import type { RefreshOptions } from "@/lib/types";

/**
 * TopBar refresh control: options popover, progress pill, polling.
 * No login gate here — `middleware.ts` already requires a valid site-login
 * session for every page, so any signed-in user can trigger a refresh.
 */
export function RefreshButton() {
  const { status, pollStatus, message, setMessage, activeUpdatedCount } = useRefreshStatus();
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [discover, setDiscover] = useState(false);
  const [force, setForce] = useState(false);
  const [starting, setStarting] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!optionsOpen) return;
    function onClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setOptionsOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [optionsOpen]);

  async function startRun() {
    setStarting(true);
    setMessage(null);
    try {
      const body: Partial<RefreshOptions> = { discover, force };
      const res = await fetch("/api/admin/refresh", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 409) {
        setMessage("A refresh is already running");
      } else if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { detail?: string } | null;
        setMessage(data?.detail ?? "Failed to start refresh");
      } else {
        setOptionsOpen(false);
      }
      await pollStatus();
    } finally {
      setStarting(false);
    }
  }

  const active = status?.active ?? null;
  const busy = starting || active != null;

  return (
    <div className="relative flex items-center gap-2" ref={popoverRef}>
      <RunStatusPill lastRun={status?.last ?? null} dataSyncedAt={status?.data_synced_at ?? null} />

      {busy ? (
        <span className="inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Refreshing
          {active ? ` · ${active.outcomes.length} · ${activeUpdatedCount} updated` : "…"}
        </span>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setOptionsOpen((v) => !v)}
          className="gap-1.5 text-xs"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh data
          <ChevronDown className="h-3 w-3" />
        </Button>
      )}

      {optionsOpen ? (
        <RefreshOptionsPopover
          discover={discover}
          onDiscoverChange={setDiscover}
          force={force}
          onForceChange={setForce}
          starting={starting}
          onStart={() => void startRun()}
        />
      ) : null}

      {message ? (
        <div
          role="status"
          className={cn(
            "absolute right-0 top-full z-30 mt-2 w-72 rounded-md border border-border bg-bg-surface p-3 text-xs text-fg-muted shadow-lg",
          )}
        >
          {message}
        </div>
      ) : null}
    </div>
  );
}
