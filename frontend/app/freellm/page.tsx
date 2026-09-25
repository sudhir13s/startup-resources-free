import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { FreeLLMChain, type CatalogResponse } from "@/components/FreeLLMChain";
import { backendGet } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function FreeLLMChainPage() {
  const result = await backendGet<CatalogResponse>("/api/freellm/catalog");

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
              The catalog `freellm/` knows about, across 7 modalities. Each
              tab shows the routing chain that fires when the dashboard
              calls an LLM — the router picks the first provider whose env
              var is present and quota intact, falling through on failure.
            </p>
          </header>

          <SubTabs />

          {result.ok ? (
            <>
              <div className="font-mono text-[10px] text-fg-subtle">
                {result.data.total} provider entries ·{" "}
                {result.data.modalities.length} modalities
              </div>
              <FreeLLMChain catalog={result.data} />
            </>
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
