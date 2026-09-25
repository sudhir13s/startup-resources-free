"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardTile } from "@/components/catalog/CardTile";
import { CategoryChips } from "@/components/catalog/CategoryChips";
import { ProviderCardFooter, GeoBadge } from "@/components/catalog/CardFooter";
import { ProviderDetail } from "@/components/ProviderDetail";
import { cn } from "@/lib/utils";
import type { ProviderRecord } from "@/lib/types";
import { tierLabel } from "@/lib/catalog/labels";

/** Card for the /funds view (startup credits / grants / accelerators /
 * perks). Amber left-edge accent differentiates from ResourceCard at a
 * glance in any mixed listing (e.g. a future Compare view). */
export function FundCard({ provider }: { provider: ProviderRecord }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const tiers = provider.use_case_tiers;
  const fitFirst = tiers[0] ?? null;
  const fitLast = tiers.length > 0 ? tiers[tiers.length - 1] : null;
  const showRange = fitFirst && fitLast && fitFirst !== fitLast;
  const initial = provider.name.charAt(0).toUpperCase();
  const primarySource = provider.source_urls[0] ?? null;

  return (
    <>
      <Card
        role="button"
        tabIndex={0}
        onClick={() => setDetailOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setDetailOpen(true);
          }
        }}
        aria-haspopup="dialog"
        aria-label={`Open details for ${provider.name}`}
        className={cn(
          "relative flex h-full cursor-pointer flex-col overflow-hidden transition-colors",
          "border-l-4 border-l-warn",
          "hover:bg-warn/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warn"
        )}
      >
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-warn/10 font-mono text-sm font-semibold text-warn">
                {initial}
              </div>
              <div className="flex min-w-0 flex-col gap-0.5">
                <CardTitle className="truncate">{provider.name}</CardTitle>
                <span className="truncate text-[11px] text-fg-subtle">{provider.vendor}</span>
              </div>
            </div>
            <button
              type="button"
              aria-label="Save (coming soon)"
              disabled
              title="Save (coming soon)"
              onClick={(e) => e.stopPropagation()}
              className="text-fg-subtle hover:text-warn disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Star className="h-4 w-4" />
            </button>
          </div>

          <CategoryChips primary={provider.category} categories={provider.categories} />

          <div className="flex flex-wrap items-center gap-1">
            <Badge variant="outline" className="font-mono">
              {provider.offer_type}
            </Badge>
            {provider.india_accessible ? (
              <Badge variant="india" aria-label="Works in India">
                <span className="mr-0.5" aria-hidden="true">📍</span>
                India
              </Badge>
            ) : null}
            {fitFirst ? (
              <Badge variant="success" className="gap-1">
                <span className="font-semibold">{tierLabel(fitFirst)}</span>
                {showRange && fitLast ? (
                  <>
                    <span aria-hidden="true">→</span>
                    <span className="font-semibold">{tierLabel(fitLast)}</span>
                  </>
                ) : null}
              </Badge>
            ) : null}
          </div>

          <p
            className="text-sm font-medium leading-snug text-fg"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
            title={provider.headline}
          >
            {provider.headline}
          </p>
        </CardHeader>

        <CardContent>
          <div className="grid grid-cols-3 gap-1.5">
            <CardTile label="Amount" value={provider.quota_summary} />
            <CardTile label="Duration" value={provider.duration_summary} />
            <CardTile label="Eligibility" value={provider.eligibility_summary} />
          </div>

          <GeoBadge geo={provider.geo_priority} />
        </CardContent>

        <CardFooter className="pt-0">
          <ProviderCardFooter
            confidence={provider.parse_confidence}
            lastVerifiedAt={provider.last_verified_at}
            primarySourceUrl={primarySource}
            detailsLabel="Apply / Details"
            accentClass="border-warn/40 bg-warn/10 text-warn hover:bg-warn/15 focus-visible:ring-warn"
            onOpenDetails={() => setDetailOpen(true)}
          />
        </CardFooter>
      </Card>

      <ProviderDetail providerId={provider.provider_id} record={provider} open={detailOpen} onOpenChange={setDetailOpen} />
    </>
  );
}
