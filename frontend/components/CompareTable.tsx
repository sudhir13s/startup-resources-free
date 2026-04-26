import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  TIER_LABELS,
  type Provider,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

type Row = {
  key: string;
  label: string;
  render: (p: Provider) => React.ReactNode;
  toString: (p: Provider) => string;
};

const ROWS: Row[] = [
  {
    key: "category",
    label: "Category",
    render: (p) => CATEGORY_LABELS[p.category] ?? p.category,
    toString: (p) => CATEGORY_LABELS[p.category] ?? p.category,
  },
  {
    key: "headline",
    label: "Headline",
    render: (p) => p.headline,
    toString: (p) => p.headline,
  },
  {
    key: "quota_summary",
    label: "Free quota",
    render: (p) => p.quota_summary,
    toString: (p) => p.quota_summary,
  },
  {
    key: "duration_summary",
    label: "Duration",
    render: (p) => p.duration_summary,
    toString: (p) => p.duration_summary,
  },
  {
    key: "region_summary",
    label: "Region",
    render: (p) => p.region_summary,
    toString: (p) => p.region_summary,
  },
  {
    key: "offer_type",
    label: "Offer type",
    render: (p) => <span className="font-mono">{p.offer_type}</span>,
    toString: (p) => p.offer_type,
  },
  {
    key: "eligibility_summary",
    label: "Eligibility",
    render: (p) => p.eligibility_summary,
    toString: (p) => p.eligibility_summary,
  },
  {
    key: "use_case_tiers",
    label: "Fits tiers",
    render: (p) => (
      <div className="flex flex-wrap gap-1">
        {p.use_case_tiers.map((t) => (
          <Badge key={t} variant="default" className="text-[10px]">
            {TIER_LABELS[t]}
          </Badge>
        ))}
      </div>
    ),
    toString: (p) => p.use_case_tiers.join(", "),
  },
  {
    key: "india_accessible",
    label: "India accessible",
    render: (p) =>
      p.india_accessible ? (
        <Badge variant="india">📍 yes</Badge>
      ) : (
        <span className="text-fg-subtle">no</span>
      ),
    toString: (p) => (p.india_accessible ? "yes" : "no"),
  },
  {
    key: "geo_priority",
    label: "Geo priority",
    render: (p) => p.geo_priority,
    toString: (p) => p.geo_priority,
  },
  {
    key: "parse_confidence",
    label: "Confidence",
    render: (p) => (
      <span
        className={cn(
          "rounded px-1.5 py-0.5 font-mono text-[10px] uppercase",
          p.parse_confidence === "high" && "bg-ok/15 text-ok",
          p.parse_confidence === "medium" && "bg-warn/15 text-warn",
          p.parse_confidence === "low" && "bg-bad/15 text-bad"
        )}
      >
        {p.parse_confidence}
      </span>
    ),
    toString: (p) => p.parse_confidence,
  },
  {
    key: "source",
    label: "Source",
    render: (p) => (
      <a
        href={p.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="break-all text-accent hover:underline"
      >
        {p.source_url}
      </a>
    ),
    toString: (p) => p.source_url,
  },
];

export function CompareTable({ providers }: { providers: Provider[] }) {
  if (providers.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <p className="text-sm text-fg-muted">
          Pick at least 2 providers to compare side-by-side.
        </p>
      </div>
    );
  }

  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-bg-base">
          <tr>
            <th
              scope="col"
              className="sticky left-0 z-20 min-w-[160px] border-b border-r border-border bg-bg-base px-3 py-2 text-left font-mono text-[10px] uppercase tracking-wider text-fg-subtle"
            >
              Field
            </th>
            {providers.map((p) => (
              <th
                key={p.id}
                scope="col"
                className="min-w-[200px] border-b border-border px-3 py-2 text-left font-semibold text-fg"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-border bg-bg-tile font-mono text-xs font-semibold text-fg-muted">
                    {p.name.charAt(0)}
                  </span>
                  {p.name}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => {
            // Diff highlighting: cell differs from any other in this row
            const values = providers.map((p) => r.toString(p));
            const allEqual = values.every((v) => v === values[0]);
            return (
              <tr key={r.key}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 border-b border-r border-border bg-bg-base px-3 py-3 text-left align-top font-mono text-xs font-medium text-fg-muted"
                >
                  {r.label}
                </th>
                {providers.map((p, i) => {
                  const differs = !allEqual && values[i] !== values[0];
                  return (
                    <td
                      key={p.id}
                      className={cn(
                        "border-b border-border px-3 py-3 align-top text-xs",
                        differs && "bg-warn/10",
                        !differs && "text-fg-muted"
                      )}
                    >
                      {r.render(p)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
