import { Suspense } from "react";
import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import {
  FundsSidebar,
  fundKindSlugs,
  type FundKind,
} from "@/components/FundsSidebar";
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

const KIND_TO_SLUGS: Record<FundKind, string[]> = {
  grant: ["grant", "grants"],
  credit: ["startup-credit", "startup-credits"],
  accelerator: ["accelerator", "accelerators"],
  perk: ["perk", "perks"],
};

function countByKind(items: Provider[]): Record<FundKind, number> {
  const counts: Record<FundKind, number> = {
    grant: 0,
    credit: 0,
    accelerator: 0,
    perk: 0,
  };
  for (const p of items) {
    for (const [key, slugs] of Object.entries(KIND_TO_SLUGS) as [
      FundKind,
      string[],
    ][]) {
      if (slugs.includes(p.category)) {
        counts[key] += 1;
        break;
      }
    }
  }
  return counts;
}

function getAll(
  searchParams: Record<string, string | string[] | undefined> | undefined,
  key: string,
): string[] {
  if (!searchParams) return [];
  const v = searchParams[key];
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

export default async function FundsPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const data = await fetchAllProviders();
  const all = data?.items ?? [];
  // Sprint #5: discriminate via `card_variant` (backend-computed). Falls
  // back to a category-based check if an older snapshot is on the wire.
  const fundsAll = all.filter((p) => providerCardVariant(p) === "funds");

  const region =
    typeof searchParams?.region === "string" ? searchParams.region : undefined;
  const kindKeys = getAll(searchParams, "fund_kind");

  // Apply region filter first (it shapes kind counts).
  let items = fundsAll;
  if (region === "india") {
    items = items.filter((p) => p.india_accessible);
  }

  // Compute kind-counts BEFORE the kind filter so the sidebar shows the
  // total available within the chosen region.
  const kindCounts = countByKind(items);

  // Apply kind filter (multi-select; empty = all kinds).
  if (kindKeys.length > 0) {
    const acceptSlugs = new Set(fundKindSlugs(kindKeys));
    items = items.filter((p) => acceptSlugs.has(p.category));
  }

  const summary = summarize(items);

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      {/* Filters LEFT, content CENTER. Outer wrapper bounds the layout to
          laptop-target width and centers it on wider screens. */}
      <div className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col md:flex-row">
        <FundsSidebar kindCounts={kindCounts} />

        <main id="main" className="flex-1 px-4 py-6 sm:px-5 lg:pl-6 lg:pr-6">
          <div className="flex flex-col gap-5">
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
                      Reset the kind / region filters or wait for the cron
                      to surface new programs.
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
