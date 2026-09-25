import Link from "next/link";
import { notFound } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { RunOutcomesTable } from "@/components/runs/RunOutcomesTable";
import { backendGet } from "@/lib/api";
import { relativeTime } from "@/lib/utils";
import type { RunReport } from "@/lib/types";

export const dynamic = "force-dynamic";

function durationLabel(run: RunReport): string {
  if (!run.finished_at) return "in progress";
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
  if (ms < 0) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export default async function RunDetailPage({ params }: { params: { runId: string } }) {
  const result = await backendGet<RunReport>(`/api/runs/${params.runId}`);

  if (!result.ok && result.status === 404) {
    notFound();
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <div>
            <Link href="/runs" className="text-xs text-accent hover:underline">
              ← All runs
            </Link>
          </div>

          {result.ok ? (
            <RunDetail run={result.data} />
          ) : (
            <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
              <p className="font-semibold">Could not load run.</p>
              <p className="mt-1 text-bad/80">{result.detail}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function RunDetail({ run }: { run: RunReport }) {
  return (
    <>
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-lg font-semibold tracking-tight text-fg">{run.run_id}</h1>
          <RunStatusBadge status={run.status} />
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-xl border border-border bg-bg-surface p-4 text-xs sm:grid-cols-4">
          <SummaryItem label="Trigger" value={run.trigger} />
          <SummaryItem label="Started" value={relativeTime(run.started_at)} title={run.started_at} />
          <SummaryItem label="Duration" value={durationLabel(run)} />
          <SummaryItem label="Providers" value={String(run.outcomes.length)} />
          <SummaryItem label="Candidates found" value={String(run.candidates_found)} />
          <SummaryItem label="LLM calls" value={String(run.llm_calls)} />
          <SummaryItem label="Search calls" value={String(run.search_calls)} />
          <SummaryItem label="Data pushed" value={run.data_pushed ? "yes" : "no"} />
        </dl>
        {run.errors.length > 0 ? (
          <div className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-xs text-bad">
            <p className="mb-1 font-semibold">{run.errors.length} run-level error{run.errors.length === 1 ? "" : "s"}</p>
            <ul className="list-disc pl-4">
              {run.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </header>

      <RunOutcomesTable outcomes={run.outcomes} />
    </>
  );
}

function SummaryItem({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="flex flex-col gap-0.5" title={title}>
      <dt className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">{label}</dt>
      <dd className="text-fg">{value}</dd>
    </div>
  );
}
