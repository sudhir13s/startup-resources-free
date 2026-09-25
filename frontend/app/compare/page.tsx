import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { CompareSelector } from "@/components/CompareSelector";
import { CompareTable } from "@/components/CompareTable";
import { backendGet, resolveBackendUrl } from "@/lib/api";
import type { ProvidersResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

function parseIds(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.flatMap((v) => v.split(",")).filter(Boolean);
  return value.split(",").filter(Boolean);
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams?: { ids?: string | string[] };
}) {
  const ids = parseIds(searchParams?.ids);
  const result = await backendGet<ProvidersResponse>("/api/providers", {});
  const all = result.ok ? result.data.items : [];
  const orderedIds = ids.filter((id) => all.some((p) => p.provider_id === id));
  const selected = orderedIds
    .map((id) => all.find((p) => p.provider_id === id))
    .filter((p): p is NonNullable<typeof p> => p !== undefined);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">Compare</h1>
            <p className="text-sm text-fg-muted">
              Pin up to 6 providers, see the side-by-side. Differing cells highlighted.
            </p>
          </header>

          <SubTabs />

          {result.ok ? (
            <>
              <CompareSelector allProviders={all} pinnedIds={orderedIds} />
              <CompareTable providers={selected} />
            </>
          ) : (
            <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
              <p className="font-semibold">Backend unreachable.</p>
              <p className="mt-1 text-bad/80">
                FastAPI service at <code className="font-mono text-xs">{resolveBackendUrl()}</code> not
                responding.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
