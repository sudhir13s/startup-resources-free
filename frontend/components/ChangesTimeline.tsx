import Link from "next/link";
import {
  ArrowDown,
  ArrowUp,
  Sparkles,
  CircleX,
  Info,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChangeSeverity, FieldChange } from "@/lib/types";

const SEVERITY_META: Record<
  ChangeSeverity,
  { label: string; variant: "success" | "warning" | "danger" | "default" | "muted"; Icon: typeof ArrowUp }
> = {
  new: { label: "New", variant: "default", Icon: Sparkles },
  improved: { label: "Improved", variant: "success", Icon: ArrowUp },
  reduced: { label: "Reduced", variant: "warning", Icon: ArrowDown },
  ended: { label: "Ended", variant: "danger", Icon: CircleX },
  metadata: { label: "Metadata", variant: "muted", Icon: Info },
};

const FIELD_LABELS: Record<string, string> = {
  __provider__: "Provider listing",
  headline: "Headline",
  quota_summary: "Free quota",
  duration_summary: "Duration",
  region_summary: "Region",
  offer_type: "Offer type",
  eligibility_summary: "Eligibility",
  use_case_tiers: "Project tiers",
  geo_priority: "Geo priority",
  parse_confidence: "Parse confidence",
  status: "Status",
};

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

function dayKey(isoDateTime: string): string {
  return isoDateTime.slice(0, 10);
}

export function ChangesTimeline({ items }: { items: FieldChange[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <h3 className="text-base font-semibold text-fg">No changes yet</h3>
        <p className="mt-2 max-w-md mx-auto text-sm text-fg-muted">
          The Changes tab fills in once a refresh run detects a field-level
          difference against the previous version of a record. Trigger a
          refresh from the TopBar to get started.
        </p>
      </div>
    );
  }

  const byDate: { date: string; items: FieldChange[] }[] = [];
  for (const c of items) {
    const date = dayKey(c.detected_at);
    const last = byDate[byDate.length - 1];
    if (last && last.date === date) {
      last.items.push(c);
    } else {
      byDate.push({ date, items: [c] });
    }
  }

  return (
    <ol className="flex flex-col gap-6">
      {byDate.map((g) => (
        <li key={g.date} className="flex flex-col gap-3">
          <div className="flex items-baseline gap-3">
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              {g.date}
            </h2>
            <span className="font-mono text-[10px] text-fg-subtle">
              · {g.items.length} {g.items.length === 1 ? "change" : "changes"}
            </span>
          </div>
          <ul className="flex flex-col gap-2">
            {g.items.map((c, i) => {
              const meta = SEVERITY_META[c.severity];
              const Icon = meta.Icon;
              return (
                <li
                  key={`${c.provider_id}-${c.field}-${i}`}
                  className={cn(
                    "flex flex-col gap-2 rounded-lg border border-border bg-bg-surface p-4",
                    "sm:flex-row sm:items-center sm:gap-4"
                  )}
                >
                  <Badge variant={meta.variant} className="self-start gap-1">
                    <Icon className="h-3 w-3" aria-hidden="true" />
                    {meta.label}
                  </Badge>
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
                      <Link
                        href={`/resources?q=${encodeURIComponent(c.provider_name)}`}
                        className="font-semibold text-fg hover:text-accent hover:underline"
                      >
                        {c.provider_name}
                      </Link>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                        {c.category}
                      </span>
                      <span className="text-fg-subtle">·</span>
                      <span className="text-xs text-fg-muted">
                        {FIELD_LABELS[c.field] ?? c.field}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 gap-x-3 gap-y-0.5 text-xs sm:grid-cols-[max-content_1fr] sm:items-baseline">
                      <span className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
                        was
                      </span>
                      <span className="text-fg-subtle line-through">
                        {formatValue(c.old_value)}
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
                        now
                      </span>
                      <span className="text-fg">{formatValue(c.new_value)}</span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}
