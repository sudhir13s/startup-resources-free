"use client";

import { useMemo, useState } from "react";
import { OutcomeStatusBadge } from "@/components/runs/RunStatusBadge";
import { cn } from "@/lib/utils";
import type { OutcomeStatus, ProviderOutcome } from "@/lib/types";

const STATUS_ORDER: OutcomeStatus[] = [
  "failed",
  "queued-verify",
  "new",
  "updated",
  "skipped",
  "unchanged",
];

function sortFailuresFirst(outcomes: ProviderOutcome[]): ProviderOutcome[] {
  const rank = new Map(STATUS_ORDER.map((s, i) => [s, i]));
  return [...outcomes].sort((a, b) => (rank.get(a.status) ?? 99) - (rank.get(b.status) ?? 99));
}

export function RunOutcomesTable({ outcomes }: { outcomes: ProviderOutcome[] }) {
  const [filter, setFilter] = useState<OutcomeStatus | "all">("all");
  const sorted = useMemo(() => sortFailuresFirst(outcomes), [outcomes]);
  const visible = filter === "all" ? sorted : sorted.filter((o) => o.status === filter);

  const availableStatuses = STATUS_ORDER.filter((s) => outcomes.some((o) => o.status === s));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by status">
        <FilterChip label={`All (${outcomes.length})`} active={filter === "all"} onClick={() => setFilter("all")} />
        {availableStatuses.map((status) => {
          const count = outcomes.filter((o) => o.status === status).length;
          return (
            <FilterChip
              key={status}
              label={`${status} (${count})`}
              active={filter === status}
              onClick={() => setFilter(status)}
            />
          );
        })}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead className="border-b border-border bg-bg-surface text-[10px] uppercase tracking-wider text-fg-subtle">
            <tr>
              <th className="px-4 py-2.5 font-medium">Provider</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Message</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
              <th className="px-4 py-2.5 font-medium">LLM provider</th>
              <th className="px-4 py-2.5 font-medium">Changes</th>
              <th className="px-4 py-2.5 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {visible.map((o) => (
              <tr key={o.provider_id} className="align-top hover:bg-bg-tile">
                <td className="px-4 py-3 font-medium text-fg">{o.provider_id}</td>
                <td className="px-4 py-3">
                  <OutcomeStatusBadge status={o.status} />
                </td>
                <td className="max-w-xs px-4 py-3 text-xs text-fg-muted">{o.message || "—"}</td>
                <td className="px-4 py-3 text-xs">
                  {o.source_url ? (
                    <a
                      href={o.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      source ↗
                    </a>
                  ) : (
                    <span className="text-fg-subtle">—</span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-fg-muted">{o.llm_provider ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs text-fg-muted">{o.changes}</td>
                <td className="px-4 py-3 font-mono text-xs text-fg-muted">{o.duration_ms}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        active
          ? "border-accent bg-accent/10 text-accent"
          : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile",
      )}
    >
      {label}
    </button>
  );
}
