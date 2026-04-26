import {
  ArrowDown,
  ArrowUp,
  Sparkles,
  CircleX,
  CircleDashed,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  relativeTime,
  type Change,
  type ChangeSeverity,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

const SEVERITY_META: Record<
  ChangeSeverity,
  { label: string; variant: "success" | "warning" | "danger" | "default" | "muted"; Icon: typeof ArrowUp }
> = {
  new: { label: "New", variant: "default", Icon: Sparkles },
  improved: { label: "Improved", variant: "success", Icon: ArrowUp },
  reduced: { label: "Reduced", variant: "warning", Icon: ArrowDown },
  ended: { label: "Ended", variant: "danger", Icon: CircleX },
  unchanged: { label: "—", variant: "muted", Icon: CircleDashed },
};

const FIELD_LABELS: Record<string, string> = {
  __provider__: "Provider listing",
  headline: "Headline",
  free_tier_summary: "Free-tier summary",
  quota_summary: "Free quota",
  duration_summary: "Duration",
  region_summary: "Region",
  offer_type: "Offer type",
  eligibility_summary: "Eligibility",
  use_case_tiers: "Project tiers",
  india_accessible: "India accessibility",
  geo_priority: "Geo priority",
  parse_confidence: "Parse confidence",
};

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export function ChangesTimeline({ items }: { items: Change[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <h3 className="text-base font-semibold text-fg">No changes yet</h3>
        <p className="mt-2 max-w-md mx-auto text-sm text-fg-muted">
          The Changes tab fills in once the daily refresh cron writes its
          first delta snapshot. The cron starts running once at least one
          free-LLM provider key (e.g. <code className="font-mono">GROQ_API_KEY</code>) is
          set in the API service&apos;s environment.
        </p>
        <p className="mt-3 text-xs text-fg-subtle">
          Until then, today&apos;s seed snapshot is the baseline.
        </p>
      </div>
    );
  }

  // Group by snapshot_date for visual rhythm.
  const byDate: { date: string; items: Change[] }[] = [];
  for (const c of items) {
    const last = byDate[byDate.length - 1];
    if (last && last.date === c.snapshot_date) {
      last.items.push(c);
    } else {
      byDate.push({ date: c.snapshot_date, items: [c] });
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
            <span className="text-[10px] text-fg-subtle">
              {relativeTime(`${g.date}T00:00:00Z`)}
            </span>
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
                      <span className="font-semibold text-fg">{c.provider_name}</span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                        {CATEGORY_LABELS[c.category] ?? c.category}
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
