"use client";

import { useMemo, useState } from "react";
import { CandidateCard } from "@/components/refresh/CandidateCard";
import { cn } from "@/lib/utils";
import type { Candidate, CandidateStatus } from "@/lib/types";

const TABS: { key: CandidateStatus; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

export function CandidatesList({ initial }: { initial: Candidate[] }) {
  const [candidates, setCandidates] = useState(initial);
  const [tab, setTab] = useState<CandidateStatus>("pending");

  const counts = useMemo(() => {
    const map: Record<CandidateStatus, number> = { pending: 0, approved: 0, rejected: 0, imported: 0 };
    for (const c of candidates) map[c.status] += 1;
    return map;
  }, [candidates]);

  const visible = candidates.filter((c) => c.status === tab);

  function handleResolved(id: string, status: Candidate["status"]) {
    setCandidates((prev) => prev.map((c) => (c.candidate_id === id ? { ...c, status } : c)));
  }

  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label="Candidate status" className="flex items-center gap-2 border-b border-border">
        {TABS.map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.key)}
              className={cn(
                "-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                active ? "border-accent text-fg" : "border-transparent text-fg-subtle hover:text-fg",
              )}
            >
              {t.label}
              <span className="rounded bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {counts[t.key]}
              </span>
            </button>
          );
        })}
      </div>

      {visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
          <h3 className="text-base font-semibold text-fg">No {tab} candidates</h3>
          <p className="mt-2 text-sm text-fg-muted">
            Run a refresh with &quot;Also discover new providers&quot; enabled to find more.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {visible.map((c) => (
            <CandidateCard key={c.candidate_id} candidate={c} onResolved={handleResolved} />
          ))}
        </div>
      )}
    </div>
  );
}
