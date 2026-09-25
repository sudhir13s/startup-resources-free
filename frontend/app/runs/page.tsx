import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { RunsTable } from "@/components/runs/RunsTable";
import { backendGet } from "@/lib/api";
import type { RunReport } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const result = await backendGet<RunReport[]>("/api/runs", { limit: 50 });

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">Runs</h1>
            <p className="text-sm text-fg-muted">
              History of refresh runs triggered from the dashboard — status, trigger,
              timing, and per-provider outcome counts.
            </p>
          </header>

          <SubTabs />

          {result.ok ? (
            <RunsTable runs={result.data} />
          ) : (
            <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
              <p className="font-semibold">Backend unreachable.</p>
              <p className="mt-1 text-bad/80">{result.detail}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
