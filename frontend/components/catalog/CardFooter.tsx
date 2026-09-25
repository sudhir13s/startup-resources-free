import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, hostnameOf, relativeTime } from "@/lib/utils";
import { CONFIDENCE_DOT_CLASS, CONFIDENCE_LABELS } from "@/lib/catalog/labels";
import type { ParseConfidence } from "@/lib/types";

/** Shared card footer: confidence dot + verified date on the left,
 * primary source link + Details button on the right. */
export function ProviderCardFooter({
  confidence,
  lastVerifiedAt,
  primarySourceUrl,
  detailsLabel,
  accentClass,
  onOpenDetails,
}: {
  confidence: ParseConfidence;
  lastVerifiedAt: string | null;
  primarySourceUrl: string | null;
  detailsLabel: string;
  accentClass: string;
  onOpenDetails: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 pt-2">
      <div className="flex min-w-0 items-center gap-3">
        <span
          className="flex items-center gap-1.5 font-mono text-[10px] text-fg-subtle"
          title={`${CONFIDENCE_LABELS[confidence]} confidence`}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", CONFIDENCE_DOT_CLASS[confidence])} aria-hidden="true" />
          {CONFIDENCE_LABELS[confidence]}
        </span>
        <span className="truncate font-mono text-[10px] text-fg-subtle">
          verified {relativeTime(lastVerifiedAt)}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {primarySourceUrl ? (
          <a
            href={primarySourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-accent"
            title={hostnameOf(primarySourceUrl)}
          >
            Source
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : null}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpenDetails();
          }}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-2",
            accentClass
          )}
          aria-haspopup="dialog"
        >
          {detailsLabel}
        </button>
      </div>
    </div>
  );
}

export function GeoBadge({ geo }: { geo: string }) {
  return (
    <Badge variant="muted" className="capitalize">
      {geo.replace(/-/g, " ")}
    </Badge>
  );
}
