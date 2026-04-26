import { Suspense } from "react";
import { TierFilterChips } from "@/components/TierFilterChips";
import {
  ProviderGrid,
  ProviderGridSkeleton,
} from "@/components/ProviderGrid";
import {
  DEFAULT_TIER,
  isTier,
  type ProvidersResponse,
  type Tier,
} from "@/lib/utils";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

async function fetchProviders(
  tier: Tier | null
): Promise<ProvidersResponse | null> {
  const url = new URL("/api/providers", BACKEND_URL);
  if (tier) url.searchParams.set("tier", tier);
  try {
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

async function fetchAllForCounts(): Promise<ProvidersResponse | null> {
  return fetchProviders(null);
}

function buildCounts(all: ProvidersResponse | null): Record<Tier, number> {
  const counts: Record<Tier, number> = {
    hobby: 0,
    personal: 0,
    "startup-mvp": 0,
    startup: 0,
  };
  if (!all) return counts;
  for (const item of all.items) {
    for (const t of item.use_case_tiers) {
      counts[t] += 1;
    }
  }
  return counts;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams?: { tier?: string };
}) {
  const tierParam = searchParams?.tier;
  const tier: Tier = isTier(tierParam) ? tierParam : DEFAULT_TIER;

  const [filtered, all] = await Promise.all([
    fetchProviders(tier),
    fetchAllForCounts(),
  ]);

  const counts = buildCounts(all);
  const indiaCount = (all?.items ?? []).filter((p) => p.india_accessible).length;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            ResourceOS
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-white/70">
            Free-tier cloud, GPU, AI APIs, databases, startup credits and
            grants — ranked by what your project actually needs.{" "}
            <span className="text-orange-300">
              Built India-primary ({indiaCount} providers work in India).
            </span>
          </p>
        </div>
        <nav
          aria-label="Primary"
          className="flex items-center gap-1 self-start font-mono text-xs text-white/60 sm:self-end"
        >
          <span className="rounded-md border border-bg-subtle bg-bg-surface px-2.5 py-1 text-white">
            Catalog
          </span>
          <span
            className="cursor-not-allowed rounded-md border border-bg-subtle/40 px-2.5 py-1 text-white/30"
            title="Coming soon"
          >
            Compare
          </span>
          <span
            className="cursor-not-allowed rounded-md border border-bg-subtle/40 px-2.5 py-1 text-white/30"
            title="Coming soon"
          >
            Changes
          </span>
          <span
            className="cursor-not-allowed rounded-md border border-bg-subtle/40 px-2.5 py-1 text-white/30"
            title="Coming soon"
          >
            Verify
          </span>
        </nav>
      </header>

      <section aria-label="Project stage filter">
        <TierFilterChips current={tier} counts={counts} />
      </section>

      <main id="main">
        <Suspense fallback={<ProviderGridSkeleton />}>
          {filtered ? (
            <ProviderGrid items={filtered.items} />
          ) : (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-200">
              <p className="font-semibold">Backend unreachable.</p>
              <p className="mt-1 text-rose-200/80">
                Check that the FastAPI service at{" "}
                <code className="font-mono">{BACKEND_URL}</code> is running
                (free-tier Render services spin down after 15 min idle —
                first request can take ~30–60 s).
              </p>
            </div>
          )}
        </Suspense>
      </main>

      <footer className="mt-6 flex flex-col gap-2 border-t border-bg-subtle pt-6 text-xs text-white/40 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Showing {filtered?.matched ?? 0} of {all?.total ?? 0} providers ·
          tier <span className="font-mono">{tier}</span> · v0.1-seed
        </span>
        <span>
          <a
            href="https://github.com/sudhir13s/startup-resources-free"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-accent"
          >
            github.com/sudhir13s/startup-resources-free
          </a>
        </span>
      </footer>
    </div>
  );
}
