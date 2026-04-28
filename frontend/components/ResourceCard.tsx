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

/** Stat tile — modality-specific. Truncates inside its row to keep the
 * card height bounded (≤ 360 px per Sprint #5 constraint). */
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

/** Best-effort extraction of a "models / capabilities" one-liner from
 * the limits dict and free-tier summary. The seed-shape `Provider` does
 * not yet expose `limits`, so we fall back to the first sentence of
 * the free-tier summary which usually mentions models or features. */
function capabilitiesLine(provider: Provider): string {
  const summary = provider.free_tier_summary ?? "";
  // Prefer a bracketed/colon-led "models" phrase when present; else
  // first 80 chars of the free-tier summary.
  const firstSentence = summary.split(/(?<=[.!])\s+/)[0] ?? summary;
  return firstSentence.length > 90
    ? firstSentence.slice(0, 87).trimEnd() + "…"
    : firstSentence;
}

/** Five stat tiles for the dense ResourceCard layout. The labels +
 * values differ per category — AI APIs surface quota / tokens / context
 * / regions / refresh cadence; everything else surfaces bandwidth /
 * storage / instances / sleep / region. We DO NOT yet extract these
 * per-modality fields from the seed, so most tiles fall back to the
 * existing summary fields with sensible labels — this gets the user's
 * "MAX info upfront" win without blocking on a schema migration. */
function resourceStatTiles(provider: Provider): { label: string; value: string }[] {
  const isAi = provider.category === "ai-api";
  if (isAi) {
    return [
      { label: "Quota", value: provider.quota_summary },
      { label: "Tokens", value: provider.duration_summary },
      { label: "Context", value: "Per provider" },
      { label: "Regions", value: provider.region_summary },
      { label: "Refresh", value: provider.duration_summary },
    ];
  }
  return [
    { label: "Bandwidth", value: provider.quota_summary },
    { label: "Storage", value: "—" },
    { label: "Instances", value: "—" },
    { label: "Sleep", value: provider.duration_summary },
    { label: "Region", value: provider.region_summary },
  ];
}

/** Resource card — used for /resources view (cloud / GPU / DB / AI APIs
 * / storage / auth / observability / OSS / learning). Densifies the
 * layout so 8+ fields are visible upfront without expanding details. */
export function ResourceCard({ provider }: { provider: Provider }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const fitFirst = tierFitFirst(provider.use_case_tiers);
  const fitLast = tierFitLast(provider.use_case_tiers);
  const showRange = fitFirst && fitLast && fitFirst !== fitLast;
  const initial = provider.name.charAt(0).toUpperCase();
  const tiles = resourceStatTiles(provider);
  const capabilities = capabilitiesLine(provider);

  return (
    <>
      <Card className="h-full max-h-[360px] overflow-hidden">
        <CardHeader>
          {/* Row 1 — logo + name + India badge + tier badges + save */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-bg-tile font-mono text-sm font-semibold text-fg-muted">
                {initial}
              </div>
              <div className="flex min-w-0 flex-col gap-0.5">
                <CardTitle className="truncate">{provider.name}</CardTitle>
                <div className="flex flex-wrap items-center gap-1">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                    {CATEGORY_LABELS[provider.category] ?? provider.category}
                  </span>
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

          {/* Row 2 — headline (1-line truncate) */}
          <p className="truncate text-sm font-medium text-fg" title={provider.headline}>
            {provider.headline}
          </p>

          {/* Row 3 — free-tier summary (2-line truncate via webkit clamp) */}
          <p
            className="text-[12px] leading-snug text-fg-muted"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
            title={provider.free_tier_summary}
          >
            {provider.free_tier_summary}
          </p>
        </CardHeader>

        <CardContent>
          {/* Row 4 — five stat tiles */}
          <div className="grid grid-cols-5 gap-1.5">
            {tiles.map((t) => (
              <StatTile key={t.label} label={t.label} value={t.value} />
            ))}
          </div>

          {/* Row 5 — capabilities one-liner */}
          <div className="flex items-baseline gap-1.5 text-[11px]">
            <span className="font-mono uppercase tracking-wider text-fg-subtle">
              Capabilities
            </span>
            <span
              className="truncate text-fg-muted"
              title={capabilities}
            >
              {capabilities}
            </span>
          </div>

          {/* Row 6 — eligibility one-liner */}
          <div className="flex items-baseline gap-1.5 text-[11px]">
            <span className="font-mono uppercase tracking-wider text-fg-subtle">
              Eligibility
            </span>
            <span className="truncate text-fg-muted" title={provider.eligibility_summary}>
              {provider.eligibility_summary}
            </span>
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
              className="inline-flex items-center gap-1 rounded-md border border-border-strong bg-bg-tile px-2.5 py-1 text-xs font-medium text-fg hover:bg-bg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-haspopup="dialog"
            >
              Details
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
