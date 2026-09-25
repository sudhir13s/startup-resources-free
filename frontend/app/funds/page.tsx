import { Suspense } from "react";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { SubTabs } from "@/components/SubTabs";
import { ProviderGrid, ProviderGridSkeleton } from "@/components/ProviderGrid";
import { backendGet, resolveBackendUrl } from "@/lib/api";
import type { ProvidersResponse } from "@/lib/types";
import { parseCatalogFilters, buildProvidersQuery, type SearchParams } from "@/lib/catalog/params";

export const dynamic = "force-dynamic";

function summarize(items: ProvidersResponse["items"]) {
  let indiaAccessible = 0;
  let indiaNative = 0;
  const categories = new Set<string>();
  for (const p of items) {
    categories.add(p.category);
    if (p.geo_priority === "india-native") indiaNative += 1;
    else if (p.india_accessible) indiaAccessible += 1;
  }
  return { indiaAccessible, indiaNative, categoryCount: categories.size };
}

export default async function FundsPage({
  searchParams,
}: {
  searchParams?: SearchParams;
}) {
  const filters = parseCatalogFilters(searchParams);
  const query = buildProvidersQuery("funds", filters);
  const result = await backendGet<ProvidersResponse>("/api/providers", query);

  const data = result.ok ? result.data : null;
  const items = data?.items ?? [];
  const facets = data?.facets ?? null;
  const invalidFilter = !result.ok && result.status !== 0;
  const backendUnreachable = !result.ok && result.status === 0;
  const summary = summarize(items);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <div className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col md:flex-row">
        <Sidebar variant="funds" facets={facets} />

        <main id="main" className="flex-1 px-4 py-6 sm:px-5 lg:pl-6 lg:pr-6">
          <div className="flex flex-col gap-5">
            <header className="flex flex-col gap-1">
              <h1 className="text-2xl font-semibold tracking-tight text-fg">Funds &amp; Credits</h1>
              <p className="text-sm text-fg-muted">
                Non-dilutive funding + cloud credits + accelerator programs + SaaS perks. Most
                founders never apply because they don&apos;t know where to look. Apply early —
                credits stack.
              </p>
            </header>

            <SubTabs matchedCount={data?.matched} />

            <section aria-label="Summary" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryTile label="Programs" value={String(items.length)} />
              <SummaryTile label="India-native" value={String(summary.indiaNative)} />
              <SummaryTile label="Accessible from India" value={String(summary.indiaAccessible)} />
              <SummaryTile label="Categories" value={String(summary.categoryCount)} />
            </section>

            <Suspense fallback={<ProviderGridSkeleton />}>
              {invalidFilter ? (
                <div className="rounded-xl border border-warn/30 bg-warn/10 p-6 text-sm text-warn">
                  <p className="font-semibold">Invalid filter — reset.</p>
                  <p className="mt-1 text-warn/80">{result.ok ? "" : result.detail}</p>
                </div>
              ) : backendUnreachable ? (
                <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
                  <p className="font-semibold">Backend unreachable.</p>
                  <p className="mt-1 text-bad/80">
                    FastAPI service at{" "}
                    <code className="font-mono text-xs">{resolveBackendUrl()}</code> not
                    responding.
                  </p>
                </div>
              ) : items.length > 0 ? (
                <ProviderGrid items={items} />
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
                  <h3 className="text-base font-semibold text-fg">No funds in this filter</h3>
                  <p className="mt-2 text-sm text-fg-muted">
                    Reset the category / region filters or wait for the cron to surface new
                    programs.
                  </p>
                </div>
              )}
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-bg-tile px-3 py-2">
      <div className="font-mono text-[9px] font-semibold uppercase tracking-wider text-fg-subtle">
        {label}
      </div>
      <div className="text-xl font-semibold text-fg">{value}</div>
    </div>
  );
}
