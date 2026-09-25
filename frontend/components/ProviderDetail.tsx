"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { CardTile } from "@/components/catalog/CardTile";
import { CategoryChips } from "@/components/catalog/CategoryChips";
import {
  HighlightsSection,
  ServicesSection,
  CreditsSection,
  BulletSection,
} from "@/components/catalog/DetailSections";
import { EligibilitySection, ClaimStepsSection, LinksSection } from "@/components/catalog/DetailMeta";
import { RelatedOffers } from "@/components/catalog/RelatedOffers";
import { relativeTime, cn } from "@/lib/utils";
import { CONFIDENCE_DOT_CLASS, CONFIDENCE_LABELS, tierLabel } from "@/lib/catalog/labels";
import type { ProviderRecord } from "@/lib/types";

export function ProviderDetail({
  providerId,
  record,
  open,
  onOpenChange,
}: {
  providerId: string;
  record: ProviderRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!record) return null;
  const initial = record.name.charAt(0).toUpperCase();
  const isFund = record.card_variant === "funds";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        side="center"
        aria-describedby={`detail-${record.provider_id}`}
        className="h-[88vh] max-h-[88vh] w-[92vw] max-w-screen-lg overflow-y-auto rounded-xl"
      >
        <DialogHeader className="border-b border-border pb-4">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                "flex h-14 w-14 shrink-0 items-center justify-center rounded-md border font-mono text-xl font-semibold",
                isFund ? "border-warn/40 bg-warn/10 text-warn" : "border-border bg-bg-tile text-fg-muted"
              )}
            >
              {initial}
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <DialogTitle className="text-xl">{record.name}</DialogTitle>
                <span className="text-sm text-fg-subtle">{record.vendor}</span>
                <Badge variant="outline" className="font-mono">
                  {record.offer_type}
                </Badge>
              </div>
              <CategoryChips primary={record.category} categories={record.categories} />
              <DialogDescription id={`detail-${record.provider_id}`} className="text-base leading-snug text-fg">
                {record.headline}
              </DialogDescription>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                {record.use_case_tiers.map((t) => (
                  <Badge key={t} variant="success" className="font-mono">
                    Fits {tierLabel(t)}
                  </Badge>
                ))}
                <Badge variant="muted" className="capitalize">
                  {record.geo_priority.replace(/-/g, " ")}
                </Badge>
                <span
                  className="ml-2 flex items-center gap-1.5 font-mono text-[10px] text-fg-subtle"
                  title={`${CONFIDENCE_LABELS[record.parse_confidence]} confidence`}
                >
                  <span
                    className={cn("h-1.5 w-1.5 rounded-full", CONFIDENCE_DOT_CLASS[record.parse_confidence])}
                    aria-hidden="true"
                  />
                  {CONFIDENCE_LABELS[record.parse_confidence]} · verified{" "}
                  {relativeTime(record.last_verified_at)}
                </span>
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-3 gap-2">
              <CardTile label="Free quota" value={record.quota_summary} />
              <CardTile label="Duration" value={record.duration_summary} />
              <CardTile label="Region" value={record.region_summary} />
            </div>

            <HighlightsSection highlights={record.highlights} />
            <ServicesSection services={record.services} />
            <CreditsSection credits={record.credits} />
            <BulletSection title="After the free period" items={record.after_free_period} />
            <BulletSection title="Gotchas" items={record.gotchas} />
            <BulletSection title="Restrictions" items={record.restrictions} />

            <EligibilitySection
              summary={record.eligibility_summary}
              eligibility={record.eligibility}
              accessMethod={record.access_method}
            />

            {record.tier_fit_rationale ? (
              <section className="flex flex-col gap-2">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  Why this tier fit
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted">{record.tier_fit_rationale}</p>
              </section>
            ) : null}

            {record.notes ? (
              <section className="flex flex-col gap-2">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  Notes
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted">{record.notes}</p>
              </section>
            ) : null}
          </div>

          <div className="flex flex-col gap-4">
            <ClaimStepsSection steps={record.claim_steps} />
            <LinksSection links={record.links} sourceUrls={record.source_urls} />
            <RelatedOffers providerId={providerId} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
