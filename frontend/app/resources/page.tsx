import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { SubTabs } from "@/components/SubTabs";
import {
  ProviderGrid,
  ProviderGridSkeleton,
} from "@/components/ProviderGrid";
import {
  DEFAULT_TIER,
  TIERS,
  TIER_LABELS,
  isTier,
  providerCardVariant,
  resolveBackendUrl,
  type ProvidersResponse,
  type Tier,
  type ParseConfidence,
} from "@/lib/utils";
import { Suspense } from "react";

export const dynamic = "force-dynamic";

const BACKEND_URL = resolveBackendUrl();

function getAll(
  searchParams: Record<string, string | string[] | undefined> | undefined,
  key: string
): string[] {
  if (!searchParams) return [];
  const v = searchParams[key];
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

async function fetchCronStatus(): Promise<import("@/lib/utils").CronStatus | null> {
  try {
    const url = new URL("/api/cron-status", BACKEND_URL);
    const res = await fetch(url.toString(), {
      headers: { accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as import("@/lib/utils").CronStatus;
  } catch {
    return null;
  }
}

async function fetchProviders(
  params: URLSearchParams
): Promise<ProvidersResponse | null> {
  const url = new URL("/api/providers", BACKEND_URL);
  params.forEach((v, k) => url.searchParams.append(k, v));
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

const VALID_REGIONS = new Set(["india", "india-accessible"]);
const VALID_CONFIDENCE: ParseConfidence[] = ["high", "medium", "low"];

export default async function HomePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const rawTier = typeof searchParams?.tier === "string" ? searchParams.tier : undefined;
  const tier: Tier = isTier(rawTier) ? rawTier : DEFAULT_TIER;
  const categories = getAll(searchParams, "category");
  const offerTypes = getAll(searchParams, "offer_type");
  const region = (typeof searchParams?.region === "string" && VALID_REGIONS.has(searchParams.region))
    ? searchParams.region
    : "any";
  const minConfidenceRaw = typeof searchParams?.min_confidence === "string" ? searchParams.min_confidence : undefined;
  const minConfidence: ParseConfidence = (VALID_CONFIDENCE as string[]).includes(minConfidenceRaw ?? "")
    ? (minConfidenceRaw as ParseConfidence)
    : "medium";

  const filtered = new URLSearchParams();
  filtered.set("tier", tier);
  if (region === "india" || region === "india-accessible") {
    filtered.set("india", "true");
  }
  categories.forEach((c) => filtered.append("category", c));
  offerTypes.forEach((o) => filtered.append("offer_type", o));
  filtered.set("min_confidence", minConfidence);

  const [filteredResp, cronStatus] = await Promise.all([
    fetchProviders(filtered),
    fetchCronStatus(),
  ]);

  // Tier counts come from the backend (computed across the full dataset).
  const tierCountsArr = filteredResp?.tier_counts ?? [];
  const tierCounts: Record<Tier, number> = {
    hobby: 0,
    personal: 0,
    "startup-mvp": 0,
    "pre-seed": 0,
    seed: 0,
    "series-a": 0,
  };
  for (const tc of tierCountsArr) tierCounts[tc.tier] = tc.count;

  const totalProvidersTracked = filteredResp?.total ?? 0;
  // Sprint #5: this page is "things you USE" — exclude fund-style
  // records (grants / credits / accelerators / perks). Those live on
  // /funds. The discriminator is `card_variant` from the backend; we
  // fall back to the category-based helper if the backend is older.
  const matched = (filteredResp?.items ?? []).filter(
    (p) => providerCardVariant(p) === "resource"
  );

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar cronStatus={cronStatus} />

      {/* Filters LEFT, content CENTER, slide-over RIGHT — per locked layout convention.
          Outer wrapper bounds the layout to laptop-target width and centers it on
          wider screens (1080p / external monitors). On MBP 14"/16" the layout
          fills the screen; on 1920p+ it centers with side gutters. */}
      <div className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col md:flex-row">
        <Sidebar currentTier={tier} tierCounts={tierCounts} />

        <main
          id="main"
          className="flex-1 px-4 py-6 sm:px-5 lg:pl-6 lg:pr-6"
        >
          <div className="flex flex-col gap-5">
            <header className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
              <h1 className="text-2xl font-semibold tracking-tight text-fg">
                Resources
              </h1>
              <span className="font-mono text-xs text-fg-subtle">
                {totalProvidersTracked} providers tracked
              </span>
            </header>

            <SubTabs matchedCount={matched.length} />

            <div className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
              <p className="text-sm text-fg-muted">
                Showing{" "}
                <span className="font-semibold text-fg">
                  {matched.length}
                </span>{" "}
                resources fit for{" "}
                <span className="font-medium text-accent">
                  {TIER_LABELS[tier]}
                </span>
              </p>
              <div
                role="radiogroup"
                aria-label="Sort"
                className="flex items-center gap-1 rounded-md border border-border bg-bg-surface p-0.5"
              >
                <button
                  type="button"
                  aria-pressed="true"
                  className="rounded-sm bg-bg-tile px-2.5 py-1 text-xs font-medium text-fg"
                >
                  Best Fit
                </button>
                <button
                  type="button"
                  disabled
                  title="Coming soon"
                  className="cursor-not-allowed px-2.5 py-1 text-xs text-fg-subtle"
                >
                  Recently Verified
                </button>
                <button
                  type="button"
                  disabled
                  title="Coming soon"
                  className="cursor-not-allowed px-2.5 py-1 text-xs text-fg-subtle"
                >
                  A–Z
                </button>
              </div>
            </div>

            <Suspense fallback={<ProviderGridSkeleton />}>
              {filteredResp ? (
                <ProviderGrid items={matched} />
              ) : (
                <div className="rounded-xl border border-bad/30 bg-bad/10 p-6 text-sm text-bad">
                  <p className="font-semibold">Backend unreachable.</p>
                  <p className="mt-1 text-bad/80">
                    FastAPI service at{" "}
                    <code className="font-mono text-xs">{BACKEND_URL}</code>{" "}
                    is not responding. Free-tier Render Web Services spin
                    down after 15 min idle — first request can take ~30–60 s.
                    Try refreshing.
                  </p>
                </div>
              )}
            </Suspense>

            <footer className="mt-4 flex flex-col items-start justify-between gap-2 border-t border-border pt-4 text-[10px] text-fg-subtle sm:flex-row sm:items-center">
              <span className="font-mono">
                tier <span className="text-fg-muted">{tier}</span> · all 6
                tiers tracked: {TIERS.join(", ")} · v0.1-seed
              </span>
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
