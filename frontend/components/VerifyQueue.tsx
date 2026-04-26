"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  TIER_LABELS,
  type Provider,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

type Decision = "confirmed" | "rejected";

const STORAGE_KEY = "resourceos.verify.decisions";

function loadDecisions(): Record<string, Decision> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, Decision>) : {};
  } catch {
    return {};
  }
}

function saveDecisions(map: Record<string, Decision>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* localStorage disabled (Safari private mode) */
  }
}

export function VerifyQueue({ items }: { items: Provider[] }) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [cursor, setCursor] = useState(0);

  // Load persisted decisions on mount.
  useEffect(() => {
    setDecisions(loadDecisions());
  }, []);

  const queue = useMemo(
    () => items.filter((p) => !decisions[p.id]),
    [items, decisions]
  );

  // Reset cursor when queue length changes.
  useEffect(() => {
    if (cursor >= queue.length) setCursor(Math.max(0, queue.length - 1));
  }, [queue.length, cursor]);

  const decide = useCallback(
    (id: string, d: Decision) => {
      setDecisions((prev) => {
        const next = { ...prev, [id]: d };
        saveDecisions(next);
        return next;
      });
    },
    []
  );

  const reset = () => {
    setDecisions({});
    saveDecisions({});
    setCursor(0);
  };

  // Keyboard shortcuts: y = confirm, n = reject.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (queue.length === 0) return;
      if (e.target instanceof HTMLInputElement) return;
      if (e.target instanceof HTMLTextAreaElement) return;
      const current = queue[Math.min(cursor, queue.length - 1)];
      if (!current) return;
      if (e.key === "y" || e.key === "Y") {
        decide(current.id, "confirmed");
      } else if (e.key === "n" || e.key === "N") {
        decide(current.id, "rejected");
      } else if (e.key === "ArrowRight") {
        setCursor((c) => Math.min(queue.length - 1, c + 1));
      } else if (e.key === "ArrowLeft") {
        setCursor((c) => Math.max(0, c - 1));
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [queue, cursor, decide]);

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <h3 className="text-base font-semibold text-fg">
          Nothing to verify
        </h3>
        <p className="mt-2 max-w-md mx-auto text-sm text-fg-muted">
          No records currently flagged with
          {" "}<code className="font-mono">parse_confidence: low</code> or
          {" "}<code className="font-mono">medium</code>. The agentic
          extractor (v0.2) populates this queue when it&apos;s unsure
          about a scraped record.
        </p>
      </div>
    );
  }

  if (queue.length === 0) {
    const confirmedCount = Object.values(decisions).filter((d) => d === "confirmed").length;
    const rejectedCount = Object.values(decisions).filter((d) => d === "rejected").length;
    return (
      <div className="flex flex-col gap-4 rounded-xl border border-border bg-bg-surface p-8 text-center">
        <h3 className="text-base font-semibold text-fg">Queue cleared</h3>
        <p className="text-sm text-fg-muted">
          {confirmedCount} confirmed · {rejectedCount} rejected.
        </p>
        <p className="text-xs text-fg-subtle">
          Decisions saved in browser localStorage. Persistence to the
          backend ships with the v0.2 cron.
        </p>
        <div>
          <Button variant="outline" size="sm" onClick={reset}>
            Reset all decisions
          </Button>
        </div>
      </div>
    );
  }

  const current = queue[Math.min(cursor, queue.length - 1)];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between text-xs font-mono text-fg-subtle">
        <span>
          {cursor + 1} / {queue.length} in queue · {items.length - queue.length} reviewed
        </span>
        <div className="flex items-center gap-2">
          <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px]">
            y
          </kbd>
          <span>confirm</span>
          <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px]">
            n
          </kbd>
          <span>reject</span>
          <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px]">
            ←/→
          </kbd>
          <span>nav</span>
        </div>
      </div>

      <article
        key={current.id}
        className="flex flex-col gap-4 rounded-xl border border-border bg-bg-surface p-6"
      >
        <header className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md border border-border bg-bg-tile font-mono text-lg font-semibold text-fg-muted">
              {current.name.charAt(0)}
            </div>
            <div className="flex flex-col gap-0.5">
              <h2 className="text-lg font-semibold text-fg">{current.name}</h2>
              <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                {CATEGORY_LABELS[current.category] ?? current.category}
              </span>
            </div>
          </div>
          <Badge
            variant={current.parse_confidence === "low" ? "danger" : "warning"}
            className="capitalize"
          >
            {current.parse_confidence} confidence
          </Badge>
        </header>

        <p className="text-sm leading-relaxed text-fg-muted">
          {current.headline}
        </p>

        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-bg-tile p-3">
            <dt className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
              Free quota
            </dt>
            <dd className="mt-1 text-sm text-fg">{current.quota_summary}</dd>
          </div>
          <div className="rounded-md border border-border bg-bg-tile p-3">
            <dt className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
              Duration
            </dt>
            <dd className="mt-1 text-sm text-fg">{current.duration_summary}</dd>
          </div>
          <div className="rounded-md border border-border bg-bg-tile p-3">
            <dt className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
              Eligibility
            </dt>
            <dd className="mt-1 text-sm text-fg">{current.eligibility_summary}</dd>
          </div>
          <div className="rounded-md border border-border bg-bg-tile p-3">
            <dt className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
              Tier fit
            </dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              {current.use_case_tiers.map((t) => (
                <Badge key={t} variant="default" className="text-[10px]">
                  {TIER_LABELS[t]}
                </Badge>
              ))}
            </dd>
          </div>
        </dl>

        <a
          href={current.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
        >
          Open source page
          <ExternalLink className="h-3 w-3" />
        </a>

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <Button
            onClick={() => decide(current.id, "confirmed")}
            className="bg-ok text-bg-base hover:bg-ok/90"
            aria-label="Confirm this extraction (keyboard: y)"
          >
            <Check className="h-4 w-4" />
            Confirm
            <kbd className="ml-1 rounded border border-bg-base/40 px-1 font-mono text-[10px]">
              y
            </kbd>
          </Button>
          <Button
            variant="outline"
            onClick={() => decide(current.id, "rejected")}
            aria-label="Reject this extraction (keyboard: n)"
          >
            <X className="h-4 w-4" />
            Reject
            <kbd className="ml-1 rounded border border-border-strong bg-bg-tile px-1 font-mono text-[10px]">
              n
            </kbd>
          </Button>
          <span className="ml-auto flex items-center gap-1 font-mono text-[10px] text-fg-subtle">
            <button
              type="button"
              onClick={() => setCursor((c) => Math.max(0, c - 1))}
              disabled={cursor === 0}
              className={cn(
                "rounded border border-border px-2 py-1 hover:bg-bg-tile",
                cursor === 0 && "cursor-not-allowed opacity-50"
              )}
            >
              ←
            </button>
            <button
              type="button"
              onClick={() =>
                setCursor((c) => Math.min(queue.length - 1, c + 1))
              }
              disabled={cursor >= queue.length - 1}
              className={cn(
                "rounded border border-border px-2 py-1 hover:bg-bg-tile",
                cursor >= queue.length - 1 && "cursor-not-allowed opacity-50"
              )}
            >
              →
            </button>
          </span>
        </div>
      </article>
    </div>
  );
}
