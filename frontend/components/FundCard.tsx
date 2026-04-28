"use client";

import { useState } from "react";
import { ExternalLink, Star } from "lucide-react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProviderDetail } from "@/components/ProviderDetail";
import {
  CATEGORY_LABELS,
  TIER_LABELS,
  relativeTime,
  tierFitFirst,
  tierFitLast,
  type Provider,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

const CONFIDENCE_DOT: Record<Provider["parse_confidence"], string> = {
  high: "bg-ok",
  medium: "bg-warn",
  low: "bg-bad",
};

const CONFIDENCE_LABEL: Record<Provider["parse_confidence"], string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

/** Map a fund category to a short pill label. */
function fundKindLabel(category: string): string {
  if (category === "grant" || category === "grants") return "Grant";
  if (category === "startup-credit" || category === "startup-credits") return "Credit";
  if (category === "accelerator" || category === "accelerators") return "Accelerator";
  if (category === "perk" || category === "perks") return "Perk";
  return CATEGORY_LABELS[category] ?? category;
}

/** Compact stat tile for the FundCard. */
function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-border bg-bg-tile px-2 py-1.5">
      <span className="font-mono text-[9px] font-semibold uppercase leading-none tracking-wider text-fg-subtle">
        {label}
      </span>
      <span
        className="truncate text-[11px] font-medium leading-tight text-fg"
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

/** Heuristic difficulty label from the eligibility narrative + offer
 * type. Cheap signal — the schema does not yet carry an explicit
 * `difficulty` field. */
function difficultyLabel(provider: Provider): string {
  const e = (provider.eligibility_summary ?? "").toLowerCase();
  if (e.includes("any") || e.includes("most")) return "Easy";
  if (e.includes("apply") || e.includes("dpiit") || e.includes("portfolio")) {
    return "Apply";
  }
  if (e.includes("invite") || provider.offer_type === "grant") return "Hard";
  return "Apply";
}

/** Decision timeline heuristic — grants imply months; credits + perks
 * are typically quick. Schema-explicit later. */
function decisionTimeline(provider: Provider): string {
  if (provider.offer_type === "grant") return "3–6 months";
  if (provider.offer_type === "perk") return "Days";
  if (provider.offer_type === "free-credits") return "Rolling";
  if (provider.category === "accelerators" || provider.category === "accelerator") {
    return "Batch / quarterly";
  }
  return "Rolling";
}

function fundStatTiles(
  provider: Provider
): { label: string; value: string }[] {
  // `quota_summary` already carries amount text (e.g. "$500k SAFE",
  // "₹50 lakh"). Extract a short currency symbol heuristically.
  const amount = provider.quota_summary;
  let currency = "—";
  if (amount.includes("$")) currency = "USD";
  else if (amount.includes("₹")) currency = "INR";
  else if (amount.includes("€")) currency = "EUR";
  else if (amount.includes("£")) currency = "GBP";

  return [
    { label: "Amount", value: amount },
    { label: "Currency", value: currency },
    { label: "Duration", value: provider.duration_summary },
    { label: "Deadline", value: decisionTimeline(provider) },
    { label: "Difficulty", value: difficultyLabel(provider) },
  ];
}

/** Fund card — used for /funds view (grants / credits / accelerators
 * / perks). Differentiated visually by an amber left-edge accent so a
 * user scanning a mixed result list (Compare tab, future) can tell at
 * a glance which records are revenue vs spend. */
export function FundCard({ provider }: { provider: Provider }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const fitFirst = tierFitFirst(provider.use_case_tiers);
  const fitLast = tierFitLast(provider.use_case_tiers);
  const showRange = fitFirst && fitLast && fitFirst !== fitLast;
  const initial = provider.name.charAt(0).toUpperCase();
  const tiles = fundStatTiles(provider);
  const kind = fundKindLabel(provider.category);

  return (
    <>
      <Card
        className={cn(
          "relative h-full max-h-[360px] overflow-hidden",
          // Amber left-edge accent — designer's call for visual
          // differentiation from ResourceCard. `bg-warn` is the warn
          // (amber) token in the project palette.
          "border-l-4 border-l-warn"
        )}
      >
        <CardHeader>
          {/* Row 1 — logo + name + India + tier badges */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-warn/10 font-mono text-sm font-semibold text-warn">
                {initial}
              </div>
              <div className="flex min-w-0 flex-col gap-0.5">
                <CardTitle className="truncate">{provider.name}</CardTitle>
                <div className="flex flex-wrap items-center gap-1">
                  <Badge variant="warning">{kind}</Badge>
                  {provider.india_accessible ? (
                    <Badge variant="india" aria-label="Works in India">
                      <span className="mr-0.5" aria-hidden="true">
                        📍
                      </span>
                      India
                    </Badge>
                  ) : null}
                  {fitFirst ? (
                    <Badge variant="success" className="gap-1">
                      <span className="font-semibold">
                        {TIER_LABELS[fitFirst]}
                      </span>
                      {showRange && fitLast ? (
                        <>
                          <span aria-hidden="true">→</span>
                          <span className="font-semibold">
                            {TIER_LABELS[fitLast]}
                          </span>
                        </>
                      ) : null}
                    </Badge>
                  ) : null}
                </div>
              </div>
            </div>
            <button
              type="button"
              aria-label="Save (coming soon)"
              disabled
              title="Save (coming soon)"
              className="text-fg-subtle hover:text-warn disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Star className="h-4 w-4" />
            </button>
          </div>

          {/* Row 2 — sector pill + offer type */}
          <div className="flex flex-wrap items-center gap-1">
            <Badge variant="muted">
              {CATEGORY_LABELS[provider.category] ?? provider.category}
            </Badge>
            <Badge variant="outline" className="font-mono">
              {provider.offer_type}
            </Badge>
          </div>

          {/* Row 3 — headline (1-line truncate) */}
          <p
            className="truncate text-sm font-medium text-fg"
            title={provider.headline}
          >
            {provider.headline}
          </p>
        </CardHeader>

        <CardContent>
          {/* Row 4 — five stat tiles: Amount / Currency / Duration / Deadline / Difficulty */}
          <div className="grid grid-cols-5 gap-1.5">
            {tiles.map((t) => (
              <StatTile key={t.label} label={t.label} value={t.value} />
            ))}
          </div>

          {/* Row 5 — eligibility narrative (1-line truncate) */}
          <div className="flex items-baseline gap-1.5 text-[11px]">
            <span className="font-mono uppercase tracking-wider text-fg-subtle">
              Eligibility
            </span>
            <span
              className="truncate text-fg-muted"
              title={provider.eligibility_summary}
            >
              {provider.eligibility_summary}
            </span>
          </div>

          {/* Row 6 — decision timeline */}
          <div className="flex items-baseline gap-1.5 text-[11px]">
            <span className="font-mono uppercase tracking-wider text-fg-subtle">
              Decision
            </span>
            <span className="text-fg-muted">{decisionTimeline(provider)}</span>
          </div>

          <div className="flex items-center justify-end gap-3 pt-0.5">
            <a
              href={provider.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-accent"
            >
              Source
              <ExternalLink className="h-3 w-3" />
            </a>
            <button
              type="button"
              onClick={() => setDetailOpen(true)}
              className="inline-flex items-center gap-1 rounded-md border border-warn/40 bg-warn/10 px-2.5 py-1 text-xs font-medium text-warn hover:bg-warn/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warn"
              aria-haspopup="dialog"
            >
              Apply / Details
            </button>
          </div>
        </CardContent>

        <CardFooter>
          <span className="flex items-center gap-2 font-mono text-[10px] text-fg-subtle">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                CONFIDENCE_DOT[provider.parse_confidence]
              )}
              aria-hidden="true"
            />
            {CONFIDENCE_LABEL[provider.parse_confidence]}
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">
            verified {relativeTime(provider.last_verified_at)}
          </span>
        </CardFooter>
      </Card>

      <ProviderDetail
        provider={provider}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </>
  );
}
