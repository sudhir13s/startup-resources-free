import { TopBar } from "@/components/TopBar";
import { SubTabs } from "@/components/SubTabs";
import { VerifyQueue } from "@/components/VerifyQueue";
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

export default async function VerifyPage() {
  const data = await fetchAllProviders();
  // Verify queue surfaces records with parse_confidence != "high".
  // The agentic extractor (v0.2) populates these as it scrapes new
  // providers; v0.1 seed only has "huggingface" at "medium" so the
  // queue starts mostly empty.
  const queue =
    data?.items.filter((p) => p.parse_confidence !== "high") ?? [];

  return (
    <div className="flex min-h-screen flex-col bg-bg-base text-fg">
      <TopBar />

      <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-5">
          <header className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">
              Verify
            </h1>
            <p className="text-sm text-fg-muted">
              Records the extractor wasn&apos;t fully sure about. Confirm
              to lock the record at <code className="font-mono">parse_confidence: high</code>;
              reject to send it back to the scraper queue.
            </p>
          </header>

          <SubTabs />

          {data ? (
            <VerifyQueue items={queue} />
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
