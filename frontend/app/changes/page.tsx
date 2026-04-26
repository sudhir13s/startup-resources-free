import { Suspense } from "react";
import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { ChangesTimeline } from "@/components/ChangesTimeline";
import { ChangesSparkline } from "@/components/ChangesSparkline";
import { resolveBackendUrl, type ChangesResponse } from "@/lib/utils";

export const dynamic = "force-dynamic";

const BACKEND_URL = resolveBackendUrl();

async function fetchChanges(since?: string): Promise<ChangesResponse | null> {
  const url = new URL("/api/changes", BACKEND_URL);
  if (since) url.searchParams.set("since", since);
  url.searchParams.set("limit", "200");
  try {
    const res = await fetch(url.toString(), {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ChangesResponse;
  } catch {
    return null;
  }
}

function ChangesSkeleton() {
  return (
    <div role="status" aria-busy="true" className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="skeleton h-20 rounded-lg border border-border"
        />
      ))}
    </div>
  );
}

export default async function ChangesPage({
  searchParams,
}: {
  searchParams?: { since?: string };
}) {
  const since = typeof searchParams?.since === "string" ? searchParams.since : undefined;
  const data = await fetchChanges(since);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Changes
            </h1>
            <p className="text-sm text-fg-muted">
              Field-level changes between daily snapshots. Reduced quotas
              flagged in amber/red; improvements + new providers in green.
            </p>
          </header>

          <SubTabs />

          {data ? (
            <>
              <section
                aria-label="Weekly trend"
                className="rounded-xl border border-border bg-bg-surface p-4"
              >
                <ChangesSparkline items={data.items} />
              </section>

              <div className="flex items-center justify-between text-xs text-fg-subtle font-mono">
                <span>
                  {data.snapshot_dates.length} snapshot
                  {data.snapshot_dates.length === 1 ? "" : "s"} on file
                  {data.latest_snapshot ? ` · latest ${data.latest_snapshot}` : ""}
                </span>
                <span>
                  showing {data.items.length} of {data.total} change events
                </span>
              </div>

              <Suspense fallback={<ChangesSkeleton />}>
                <ChangesTimeline items={data.items} />
              </Suspense>
            </>
          ) : (
            <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
              <p className="font-semibold">Backend unreachable.</p>
              <p className="mt-1 text-bad/80">
                FastAPI service at{" "}
                <code className="font-mono text-xs">{BACKEND_URL}</code>{" "}
                not responding.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
