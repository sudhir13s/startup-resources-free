import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { FreeLLMChain } from "@/components/FreeLLMChain";
import { resolveBackendUrl } from "@/lib/utils";

export const dynamic = "force-dynamic";

const BACKEND_URL = resolveBackendUrl();

type CatalogResponse = {
  modalities: string[];
  total: number;
  by_modality: Record<string, unknown[]>;
};

async function fetchCatalog(): Promise<CatalogResponse | null> {
  try {
    const res = await fetch(new URL("/api/freellm/catalog", BACKEND_URL).toString(), {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as CatalogResponse;
  } catch {
    return null;
  }
}

export default async function FreeLLMChainPage() {
  const catalog = await fetchCatalog();

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Free-LLM Chain
            </h1>
            <p className="text-sm text-fg-muted">
              The 28-entry catalog `freellm/` knows about, across 7 modalities.
              Each tab shows the routing chain that fires when the dashboard
              calls an LLM — the router picks the first provider whose env
              var is present and quota intact, falling through on failure.
            </p>
          </header>

          <SubTabs />

          {catalog ? (
            <>
              <div className="font-mono text-[10px] text-fg-subtle">
                {catalog.total} provider entries · {catalog.modalities.length}{" "}
                modalities
              </div>
              {/* @ts-expect-error — server-fetched JSON has loose shape; component validates */}
              <FreeLLMChain catalog={catalog} />
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
