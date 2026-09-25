import { Suspense } from "react";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { SubTabs } from "@/components/SubTabs";
import { ProviderGrid, ProviderGridSkeleton } from "@/components/ProviderGrid";
import { backendGet, resolveBackendUrl } from "@/lib/api";
import type { ProvidersResponse } from "@/lib/types";
import { parseCatalogFilters, buildProvidersQuery, type SearchParams } from "@/lib/catalog/params";

export const dynamic = "force-dynamic";

export default async function ResourcesPage({
  searchParams,
}: {
  searchParams?: SearchParams;
}) {
  const filters = parseCatalogFilters(searchParams);
  const query = buildProvidersQuery("resource", filters);
  const result = await backendGet<ProvidersResponse>("/api/providers", query);

  const data = result.ok ? result.data : null;
  const items = data?.items ?? [];
  const facets = data?.facets ?? null;
  const invalidFilter = !result.ok && result.status !== 0;
  const backendUnreachable = !result.ok && result.status === 0;

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <div className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col md:flex-row">
        <Sidebar variant="resource" facets={facets} />

        <main id="main" className="flex-1 px-4 py-6 sm:px-5 lg:pl-6 lg:pr-6">
          <div className="flex flex-col gap-5">
            <header className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
              <h1 className="text-2xl font-semibold tracking-tight text-fg">Resources</h1>
              <span className="font-mono text-xs text-fg-subtle">
                {data?.total ?? 0} providers tracked
              </span>
            </header>

            <SubTabs matchedCount={data?.matched} />

            <p className="text-sm text-fg-muted">
              Showing <span className="font-semibold text-fg">{items.length}</span> resources
            </p>

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
                    <code className="font-mono text-xs">{resolveBackendUrl()}</code> is not
                    responding. Free-tier Render Web Services spin down after 15 min idle — first
                    request can take ~30–60 s. Try refreshing.
                  </p>
                </div>
              ) : (
                <ProviderGrid items={items} />
              )}
            </Suspense>

            <footer className="mt-4 flex flex-col items-start justify-between gap-2 border-t border-border pt-4 text-[10px] text-fg-subtle sm:flex-row sm:items-center">
              <span className="font-mono">v0.2 · service-aware catalog</span>
              <a
                href="https://github.com/sudhir13s/startup-resources-free"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-accent"
              >
                github.com/sudhir13s/startup-resources-free
              </a>
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}
