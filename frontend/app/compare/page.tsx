import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { CompareSelector } from "@/components/CompareSelector";
import { CompareTable } from "@/components/CompareTable";
import { resolveBackendUrl, type ProvidersResponse } from "@/lib/utils";

export const dynamic = "force-dynamic";

const BACKEND_URL = resolveBackendUrl();

async function fetchAllProviders(): Promise<ProvidersResponse | null> {
  try {
    const url = new URL("/api/providers", BACKEND_URL);
    const res = await fetch(url.toString(), {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ProvidersResponse;
  } catch {
    return null;
  }
}

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
  const data = await fetchAllProviders();
  const all = data?.items ?? [];
  const orderedIds = ids.filter((id) => all.some((p) => p.id === id));
  const selected = orderedIds
    .map((id) => all.find((p) => p.id === id))
    .filter((p): p is NonNullable<typeof p> => p !== undefined);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Compare
            </h1>
            <p className="text-sm text-fg-muted">
              Pin up to 6 providers, see the side-by-side. Differing
              cells highlighted.
            </p>
          </header>

          <SubTabs />

          {data ? (
            <>
              <CompareSelector allProviders={all} pinnedIds={orderedIds} />
              <CompareTable providers={selected} />
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
