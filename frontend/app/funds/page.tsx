import { Suspense } from "react";
import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import {
  ProviderGrid,
  ProviderGridSkeleton,
} from "@/components/ProviderGrid";
import {
  providerCardVariant,
  resolveBackendUrl,
  type ProvidersResponse,
  type Provider,
} from "@/lib/utils";

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

function summarize(items: Provider[]) {
  const byCategory = new Map<string, number>();
  let indiaAccessible = 0;
  let indiaNative = 0;
  for (const p of items) {
    byCategory.set(p.category, (byCategory.get(p.category) ?? 0) + 1);
    if (p.geo_priority === "india-native") {
      indiaNative += 1;
    } else if (p.india_accessible) {
      indiaAccessible += 1;
    }
  }
  return { byCategory, indiaAccessible, indiaNative };
}

export default async function FundsPage({
  searchParams,
}: {
  searchParams?: { region?: string };
}) {
  const data = await fetchAllProviders();
  const all = data?.items ?? [];
  // Sprint #5: discriminate via `card_variant` (backend-computed). Falls
  // back to a category-based check if an older snapshot is on the wire.
  let items = all.filter((p) => providerCardVariant(p) === "funds");

  // Region filter: ?region=india surfaces india-native + accessible-from-india.
  const region = searchParams?.region;
  if (region === "india") {
    items = items.filter((p) => p.india_accessible);
  }

  const summary = summarize(items);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Funds &amp; Credits
            </h1>
            <p className="text-sm text-fg-muted">
              Non-dilutive funding + cloud credits + accelerator programs
              + SaaS perks. Most founders never apply because they don&apos;t
              know where to look. Apply early — credits stack.
            </p>
          </header>

          <SubTabs />

          {/* Region quick-toggle */}
          <div
            role="radiogroup"
            aria-label="Region"
            className="flex items-center gap-1 rounded-md border border-border bg-bg-surface p-0.5 self-start"
          >
            <a
              href="/funds"
              role="radio"
              aria-checked={region !== "india"}
              className={
                "rounded-sm px-3 py-1 text-xs font-medium " +
                (region !== "india"
                  ? "bg-bg-tile text-fg"
                  : "text-fg-subtle hover:text-fg")
              }
            >
              All regions
            </a>
            <a
              href="/funds?region=india"
              role="radio"
              aria-checked={region === "india"}
              className={
                "rounded-sm px-3 py-1 text-xs font-medium " +
                (region === "india"
                  ? "bg-bg-tile text-fg"
                  : "text-fg-subtle hover:text-fg")
              }
            >
              India-accessible only
            </a>
          </div>

          {/* Summary strip */}
          <section
            aria-label="Summary"
            className="grid grid-cols-2 sm:grid-cols-4 gap-3"
          >
            <SummaryTile label="Programs" value={String(items.length)} />
            <SummaryTile
              label="India-native"
              value={String(summary.indiaNative)}
            />
            <SummaryTile
              label="Accessible from India"
              value={String(summary.indiaAccessible)}
            />
            <SummaryTile
              label="Categories"
              value={String(summary.byCategory.size)}
            />
          </section>

          {/* Per-category counts */}
          {summary.byCategory.size > 0 ? (
            <div
              aria-label="By category"
              className="flex flex-wrap items-center gap-1.5 text-xs"
            >
              {Array.from(summary.byCategory.entries())
                .sort((a, b) => b[1] - a[1])
                .map(([cat, n]) => (
                  <span
                    key={cat}
                    className="rounded-full border border-border bg-bg-tile px-2 py-0.5 font-mono text-fg-muted"
                  >
                    {cat}: {n}
                  </span>
                ))}
            </div>
          ) : null}

          <Suspense fallback={<ProviderGridSkeleton />}>
            {data ? (
              items.length > 0 ? (
                <ProviderGrid items={items} />
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
                  <h3 className="text-base font-semibold text-fg">
                    No funds in this filter
                  </h3>
                  <p className="mt-2 text-sm text-fg-muted">
                    Reset the region filter or wait for the daily cron to
                    surface new programs.
                  </p>
                </div>
              )
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
          </Suspense>
        </div>
      </main>
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
