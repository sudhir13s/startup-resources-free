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

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-bg-tile px-3 py-2">
      <span className="font-mono text-[9px] font-semibold uppercase tracking-wider text-fg-subtle">
        {label}
      </span>
      <span className="truncate text-xs font-medium text-fg" title={value}>
        {value}
      </span>
    </div>
  );
}

export function ProviderCard({ provider }: { provider: Provider }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const fitFirst = tierFitFirst(provider.use_case_tiers);
  const fitLast = tierFitLast(provider.use_case_tiers);
  const showRange = fitFirst && fitLast && fitFirst !== fitLast;
  const initial = provider.name.charAt(0).toUpperCase();

  return (
    <>
      <Card className="h-full">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-bg-tile font-mono text-sm font-semibold text-fg-muted">
                {initial}
              </div>
              <div className="flex flex-col gap-0.5">
                <CardTitle>{provider.name}</CardTitle>
                <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                  {CATEGORY_LABELS[provider.category] ?? provider.category}
                </span>
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

          {provider.india_accessible ? (
            <div>
              <Badge variant="india" aria-label="Works in India">
                <span className="mr-1" aria-hidden="true">📍</span>
                Works in India
              </Badge>
            </div>
          ) : null}

          <p className="text-sm leading-relaxed text-fg-muted">
            {provider.headline}
          </p>
        </CardHeader>

        <CardContent>
          <div className="grid grid-cols-3 gap-2">
            <StatTile label="Free quota" value={provider.quota_summary} />
            <StatTile label="Duration" value={provider.duration_summary} />
            <StatTile label="Region" value={provider.region_summary} />
          </div>

          {fitFirst ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="success" className="gap-1">
                Fits
                <span className="font-semibold">{TIER_LABELS[fitFirst]}</span>
                {showRange && fitLast ? (
                  <>
                    <span aria-hidden="true">→</span>
                    <span className="font-semibold">
                      {TIER_LABELS[fitLast]}
                    </span>
                  </>
                ) : null}
              </Badge>
            </div>
          ) : null}

          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs">
            <dt className="text-fg-subtle">Offer</dt>
            <dd className="font-mono text-fg">{provider.offer_type}</dd>
            <dt className="text-fg-subtle">Eligibility</dt>
            <dd className="text-fg">{provider.eligibility_summary}</dd>
          </dl>

          <div className="flex items-center justify-end gap-3 pt-1">
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
