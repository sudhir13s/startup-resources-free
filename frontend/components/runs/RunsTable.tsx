import Link from "next/link";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { relativeTime } from "@/lib/utils";
import type { RunReport } from "@/lib/types";

function durationLabel(run: RunReport): string {
  if (!run.finished_at) return "—";
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
  if (ms < 0) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function outcomeCounts(run: RunReport): string {
  const counts = new Map<string, number>();
  for (const o of run.outcomes) counts.set(o.status, (counts.get(o.status) ?? 0) + 1);
  return Array.from(counts.entries())
    .map(([status, count]) => `${count} ${status}`)
    .join(" · ");
}

export function RunsTable({ runs }: { runs: RunReport[] }) {
  if (runs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <h3 className="text-base font-semibold text-fg">No runs yet</h3>
        <p className="mt-2 text-sm text-fg-muted">
          Trigger a refresh from the TopBar to see run history here.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-border bg-bg-surface text-[10px] uppercase tracking-wider text-fg-subtle">
          <tr>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium">Trigger</th>
            <th className="px-4 py-2.5 font-medium">Started</th>
            <th className="px-4 py-2.5 font-medium">Duration</th>
            <th className="px-4 py-2.5 font-medium">Outcomes</th>
            <th className="px-4 py-2.5 font-medium">LLM calls</th>
            <th className="px-4 py-2.5 font-medium">Data pushed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {runs.map((run) => (
            <tr key={run.run_id} className="hover:bg-bg-tile">
              <td className="px-4 py-3">
                <Link href={`/runs/${run.run_id}`} className="inline-flex items-center gap-2 hover:underline">
                  <RunStatusBadge status={run.status} />
                </Link>
              </td>
              <td className="px-4 py-3 text-fg-muted">{run.trigger}</td>
              <td className="px-4 py-3 text-fg-muted" title={run.started_at}>
                {relativeTime(run.started_at)}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">{durationLabel(run)}</td>
              <td className="px-4 py-3 text-xs text-fg-muted">{outcomeCounts(run) || "—"}</td>
              <td className="px-4 py-3 font-mono text-xs text-fg-muted">{run.llm_calls}</td>
              <td className="px-4 py-3">
                <span className={run.data_pushed ? "text-ok" : "text-fg-subtle"}>
                  {run.data_pushed ? "✓" : "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
