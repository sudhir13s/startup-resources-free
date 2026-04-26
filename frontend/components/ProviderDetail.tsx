"use client";

import { ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  TIER_LABELS,
  relativeTime,
  type Provider,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

const CONFIDENCE_DOT: Record<Provider["parse_confidence"], string> = {
  high: "bg-ok",
  medium: "bg-warn",
  low: "bg-bad",
};

const CONFIDENCE_LABEL: Record<Provider["parse_confidence"], string> = {
  high: "High confidence",
  medium: "Medium confidence — verify yourself",
  low: "Low confidence — please verify the source",
};

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-bg-tile px-3 py-2">
      <span className="font-mono text-[9px] font-semibold uppercase tracking-wider text-fg-subtle">
        {label}
      </span>
      <span className="text-xs font-medium text-fg break-words">{value}</span>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[max-content_1fr] items-baseline gap-x-4 gap-y-0">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
        {label}
      </dt>
      <dd className="text-sm text-fg break-words">{children}</dd>
    </div>
  );
}

export function ProviderDetail({
  provider,
  open,
  onOpenChange,
}: {
  provider: Provider | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!provider) return null;
  const initial = provider.name.charAt(0).toUpperCase();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent side="right" aria-describedby={`detail-${provider.id}`}>
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md border border-border bg-bg-tile font-mono text-lg font-semibold text-fg-muted">
              {initial}
            </div>
            <div className="flex flex-col gap-0.5">
              <DialogTitle>{provider.name}</DialogTitle>
              <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                {CATEGORY_LABELS[provider.category] ?? provider.category}
              </span>
              <DialogDescription className="mt-1.5" id={`detail-${provider.id}`}>
                {provider.headline}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex flex-wrap gap-1.5">
          {provider.use_case_tiers.map((t) => (
            <Badge key={t} variant="default" className="font-mono">
              Fits {TIER_LABELS[t]}
            </Badge>
          ))}
          {provider.india_accessible ? (
            <Badge variant="india">📍 Works in India</Badge>
          ) : null}
          <Badge variant="muted" className="capitalize">
            {provider.geo_priority.replace(/-/g, " ")}
          </Badge>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <StatTile label="Free quota" value={provider.quota_summary} />
          <StatTile label="Duration" value={provider.duration_summary} />
          <StatTile label="Region" value={provider.region_summary} />
        </div>

        <section className="rounded-md border border-border bg-bg-tile p-4">
          <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
            Free-tier summary
          </h3>
          <p className="text-sm leading-relaxed text-fg-muted">
            {provider.free_tier_summary}
          </p>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
            Details
          </h3>
          <dl className="flex flex-col gap-2">
            <Row label="Offer">
              <span className="font-mono text-xs">{provider.offer_type}</span>
            </Row>
            <Row label="Eligibility">{provider.eligibility_summary}</Row>
            <Row label="Source">
              <a
                href={provider.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 break-all text-accent hover:underline"
              >
                {provider.source_url}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            </Row>
            <Row label="Confidence">
              <span className="inline-flex items-center gap-2">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    CONFIDENCE_DOT[provider.parse_confidence]
                  )}
                  aria-hidden="true"
                />
                {CONFIDENCE_LABEL[provider.parse_confidence]}
              </span>
            </Row>
            <Row label="Verified">{relativeTime(provider.last_verified_at)}</Row>
            {provider.notes ? <Row label="Notes">{provider.notes}</Row> : null}
          </dl>
        </section>
      </DialogContent>
    </Dialog>
  );
}
