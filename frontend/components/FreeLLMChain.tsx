"use client";

import { useEffect, useState } from "react";
import { Play, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type CatalogEntry = {
  provider: string;
  model: string;
  env_var: string;
  speed_tier: "fast" | "medium" | "slow";
  free_tier_kind: string;
  last_verified: string;
  docs_url: string | null;
  notes: string | null;
};

type CatalogResponse = {
  modalities: string[];
  total: number;
  by_modality: Record<string, CatalogEntry[]>;
};

type PlanOption = {
  provider: string;
  model: string;
  env_var_present: boolean;
  quota_remaining: string;
  speed_tier: "fast" | "medium" | "slow";
  free_tier_kind: string;
};

type PlanResponse = {
  modality: string;
  task_name: string;
  options: PlanOption[];
  chosen: PlanOption | null;
  reason_skipped: Record<string, string>;
};

const MODALITY_LABELS: Record<string, string> = {
  text: "Text (chat / completion)",
  vision: "Vision (text + image → text)",
  image_gen: "Image generation",
  video_gen: "Video generation",
  embed: "Embeddings",
  stt: "Speech-to-Text",
  tts: "Text-to-Speech",
};

const SPEED_LABEL: Record<string, string> = {
  fast: "Fast",
  medium: "Medium",
  slow: "Slow",
};

export function FreeLLMChain({ catalog }: { catalog: CatalogResponse }) {
  const [active, setActive] = useState<string>(catalog.modalities[0]);
  const [plans, setPlans] = useState<Record<string, PlanResponse | null>>({});

  useEffect(() => {
    let alive = true;
    const url = `/api/freellm/plan?modality=${encodeURIComponent(active)}&task_name=dashboard-preview`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: PlanResponse | null) => {
        if (!alive) return;
        setPlans((p) => ({ ...p, [active]: data }));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [active]);

  const plan = plans[active];
  const entries = catalog.by_modality[active] ?? [];

  return (
    <div className="flex flex-col gap-4">
      <nav
        role="tablist"
        aria-label="Modality"
        className="-mx-4 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0"
      >
        {catalog.modalities.map((m) => {
          const isActive = m === active;
          const count = catalog.by_modality[m]?.length ?? 0;
          return (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActive(m)}
              className={cn(
                "shrink-0 rounded-md border px-3 py-1.5 text-xs transition-colors",
                isActive
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile"
              )}
            >
              {MODALITY_LABELS[m] ?? m}
              <span className="ml-1.5 font-mono text-[10px] opacity-70">
                {count}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <section className="flex flex-col gap-2">
          <h2 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
            Catalog · {entries.length} {MODALITY_LABELS[active] ?? active}{" "}
            providers
          </h2>
          <ol className="flex flex-col gap-2">
            {entries.map((e, i) => (
              <li
                key={`${e.provider}-${e.model}-${i}`}
                className="flex flex-col gap-1.5 rounded-lg border border-border bg-bg-surface p-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-sm font-medium text-fg">
                    {e.provider}/{e.model}
                  </span>
                  <span className="font-mono text-[10px] text-fg-subtle">
                    verified {e.last_verified}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="muted" className="font-mono">
                    env: {e.env_var}
                  </Badge>
                  <Badge variant="outline">
                    speed: {SPEED_LABEL[e.speed_tier]}
                  </Badge>
                  <Badge variant="outline" className="font-mono">
                    {e.free_tier_kind}
                  </Badge>
                  {e.docs_url ? (
                    <a
                      href={e.docs_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-accent hover:underline"
                    >
                      docs ↗
                    </a>
                  ) : null}
                </div>
                {e.notes ? (
                  <p className="text-xs text-fg-muted">{e.notes}</p>
                ) : null}
              </li>
            ))}
          </ol>
        </section>

        <aside className="flex flex-col gap-3">
          <div className="rounded-lg border border-border bg-bg-surface p-4">
            <header className="flex items-center justify-between gap-2">
              <h2 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Routing chain · {active}
              </h2>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setPlans((p) => ({ ...p, [active]: null }));
                }}
              >
                <Play className="h-3 w-3" />
                Test
              </Button>
            </header>

            {plan === undefined ? (
              <p className="mt-2 text-xs text-fg-subtle">
                Loading routing plan…
              </p>
            ) : plan === null ? (
              <p className="mt-2 text-xs text-fg-subtle">No data.</p>
            ) : plan.chosen ? (
              <div className="mt-3 flex flex-col gap-2">
                <div className="rounded-md border border-ok/40 bg-ok/10 p-3">
                  <div className="flex items-center gap-1.5 text-xs text-ok">
                    <Zap className="h-3 w-3" />
                    Will route to
                  </div>
                  <div className="mt-1 font-mono text-sm font-medium text-fg">
                    {plan.chosen.provider}/{plan.chosen.model}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-fg-subtle">
                    {plan.chosen.quota_remaining}
                  </div>
                </div>

                {plan.options.length > 1 ? (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-fg-muted hover:text-fg">
                      {plan.options.length - 1} fallback
                      {plan.options.length === 2 ? "" : "s"} after
                    </summary>
                    <ol className="mt-2 flex flex-col gap-1 pl-4">
                      {plan.options.slice(1).map((o, i) => (
                        <li key={`${o.provider}-${o.model}-${i}`}>
                          <span className="font-mono">
                            {o.provider}/{o.model}
                          </span>
                          <span className="ml-2 text-[10px] text-fg-subtle">
                            {o.quota_remaining}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </details>
                ) : null}
              </div>
            ) : (
              <div className="mt-3 rounded-md border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
                No provider available. Add at least one of the env vars
                listed in <code className="font-mono">.env.example</code>{" "}
                to unlock the chain.
              </div>
            )}

            {plan && Object.keys(plan.reason_skipped).length > 0 ? (
              <details className="mt-3 text-xs">
                <summary className="cursor-pointer text-fg-muted hover:text-fg">
                  {Object.keys(plan.reason_skipped).length} skipped
                </summary>
                <ul className="mt-2 flex flex-col gap-1 pl-4 font-mono text-[10px] text-fg-subtle">
                  {Object.entries(plan.reason_skipped).map(([key, reason]) => (
                    <li key={key}>
                      <span className="text-fg-muted">{key}</span>: {reason}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>

          <div className="rounded-lg border border-border bg-bg-surface p-4 text-xs text-fg-muted">
            <p className="mb-2 font-semibold text-fg">$0 spend by design</p>
            <p>
              The catalog only lists providers with documented free
              tiers. The router picks the first available, falls
              through on quota or 4xx/5xx, and never auto-inserts paid
              keys. Set <code className="font-mono">LLM_ALLOW_PAID=1</code>{" "}
              to opt in.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
