"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ExternalLink, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, type VerifyQueueItem } from "@/lib/utils";

type Decision = "confirmed" | "rejected";
type RowState = {
  decision: Decision;
  loading: false;
  error?: string;
} | {
  decision: null;
  loading: true;
} | null;

/**
 * Live verify queue — talks to /api/verify-queue.
 *
 * Each row is locally optimistic: clicking Confirm/Reject flips the row
 * to a loading spinner, POSTs to the backend, and on success removes the
 * row from view. On error the row stays + shows the failure reason so
 * the user can retry. Decisions ARE NOT persisted to localStorage like
 * the seed-filtered queue — the SQLite DB is authoritative.
 */
export function LiveVerifyQueue({
  initialItems,
  apiBase,
}: {
  initialItems: VerifyQueueItem[];
  apiBase: string;
}) {
  const [items, setItems] = useState<VerifyQueueItem[]>(initialItems);
  const [states, setStates] = useState<Record<string, RowState>>({});
  const [cursor, setCursor] = useState(0);

  const visible = useMemo(
    () =>
      items.filter((it) => {
        const s = states[it.record_id];
        return !s || s.loading;
      }),
    [items, states],
  );

  useEffect(() => {
    if (cursor >= visible.length) {
      setCursor(Math.max(0, visible.length - 1));
    }
  }, [visible.length, cursor]);

  const decide = useCallback(
    async (recordId: string, decision: Decision) => {
      setStates((prev) => ({ ...prev, [recordId]: { decision: null, loading: true } }));
      const path = decision === "confirmed" ? "confirm" : "reject";
      try {
        const url = new URL(`/api/verify-queue/${recordId}/${path}`, apiBase);
        const res = await fetch(url.toString(), {
          method: "POST",
          headers: { accept: "application/json" },
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        // Drop the row from local state so the queue shrinks.
        setItems((prev) => prev.filter((it) => it.record_id !== recordId));
        setStates((prev) => {
          const next = { ...prev };
          delete next[recordId];
          return next;
        });
      } catch (err) {
        setStates((prev) => ({
          ...prev,
          [recordId]: {
            decision,
            loading: false,
            error: err instanceof Error ? err.message : "request failed",
          },
        }));
      }
    },
    [apiBase],
  );

  // Keyboard shortcuts: y/n + ←/→.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (visible.length === 0) return;
      if (e.target instanceof HTMLInputElement) return;
      if (e.target instanceof HTMLTextAreaElement) return;
      const current = visible[Math.min(cursor, visible.length - 1)];
      if (!current) return;
      if (e.key === "y" || e.key === "Y") {
        decide(current.record_id, "confirmed");
      } else if (e.key === "n" || e.key === "N") {
        decide(current.record_id, "rejected");
      } else if (e.key === "ArrowRight") {
        setCursor((c) => Math.min(visible.length - 1, c + 1));
      } else if (e.key === "ArrowLeft") {
        setCursor((c) => Math.max(0, c - 1));
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [visible, cursor, decide]);

  if (initialItems.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <h3 className="text-base font-semibold text-fg">Verify queue empty</h3>
        <p className="mt-2 max-w-md mx-auto text-sm text-fg-muted">
          The pipeline hasn&apos;t flagged any low-confidence records.
          Once the daily cron runs in <code className="font-mono">mode=auto</code>,
          uncertain extractions show up here for one-tap Confirm / Reject.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-xs text-fg-subtle font-mono">
        <span>
          {visible.length} pending · {initialItems.length - visible.length} resolved
        </span>
        <span className="text-fg-muted">
          shortcuts: <kbd className="rounded border border-border px-1">y</kbd> confirm
          {" "}<kbd className="rounded border border-border px-1">n</kbd> reject
          {" "}<kbd className="rounded border border-border px-1">←/→</kbd> navigate
        </span>
      </div>

      <ul className="flex flex-col gap-3" role="list">
        {visible.map((item, idx) => {
          const state = states[item.record_id];
          const isCursor = idx === Math.min(cursor, visible.length - 1);
          const errored = state && !state.loading && state.error;
          return (
            <li
              key={item.record_id}
              className={cn(
                "rounded-xl border bg-bg-surface p-4 transition",
                isCursor ? "border-fg" : "border-border",
                errored ? "border-bad" : "",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-fg">
                      {item.provider_name}
                    </h3>
                    <Badge variant="muted" className="font-mono text-xs">
                      {item.parse_confidence}
                    </Badge>
                  </div>
                  <p className="text-sm text-fg-muted">{item.reason}</p>
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex w-fit items-center gap-1 text-xs text-fg-subtle hover:text-fg"
                  >
                    {item.source_url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="default"
                    onClick={() => decide(item.record_id, "confirmed")}
                    disabled={state?.loading}
                    aria-label={`Confirm ${item.provider_name}`}
                  >
                    {state?.loading && state.decision === null ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                    <span className="ml-1">Confirm</span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => decide(item.record_id, "rejected")}
                    disabled={state?.loading}
                    aria-label={`Reject ${item.provider_name}`}
                  >
                    <X className="h-4 w-4" />
                    <span className="ml-1">Reject</span>
                  </Button>
                </div>
              </div>

              {errored && (
                <p className="mt-3 text-xs text-bad">
                  Failed to {state?.decision}: {state?.error}. Retry above.
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
