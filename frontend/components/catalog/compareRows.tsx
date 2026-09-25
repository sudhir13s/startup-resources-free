import { Badge } from "@/components/ui/badge";
import { hostnameOf } from "@/lib/utils";
import { categoryLabel, tierLabel } from "@/lib/catalog/labels";
import { formatCreditAmount } from "@/lib/catalog/format";
import type { ProviderRecord } from "@/lib/types";

export type CompareRow = {
  key: string;
  label: string;
  render: (p: ProviderRecord) => React.ReactNode;
  toString: (p: ProviderRecord) => string;
};

function servicesByCategory(p: ProviderRecord): string {
  const byCategory = new Map<string, number>();
  for (const s of p.services) byCategory.set(s.category, (byCategory.get(s.category) ?? 0) + 1);
  if (byCategory.size === 0) return "—";
  return [...byCategory.entries()].map(([c, n]) => `${categoryLabel(c)} (${n})`).join(", ");
}

function creditsTotal(p: ProviderRecord): string {
  if (p.credits.length === 0) return "—";
  const byCurrency = new Map<string, number>();
  for (const c of p.credits) {
    if (c.amount === null) continue;
    const cur = c.currency ?? "USD";
    byCurrency.set(cur, (byCurrency.get(cur) ?? 0) + c.amount);
  }
  const parts = [...byCurrency.entries()].map(([cur, amt]) => formatCreditAmount(amt, cur));
  return parts.length > 0 ? parts.join(" + ") : "—";
}

export const COMPARE_ROWS: CompareRow[] = [
  { key: "offer_type", label: "Offer type", render: (p) => <span className="font-mono">{p.offer_type}</span>, toString: (p) => p.offer_type },
  { key: "categories", label: "Categories", render: (p) => p.categories.map(categoryLabel).join(", "), toString: (p) => p.categories.join(", ") },
  { key: "quota_summary", label: "Free quota", render: (p) => p.quota_summary, toString: (p) => p.quota_summary },
  { key: "duration_summary", label: "Duration", render: (p) => p.duration_summary, toString: (p) => p.duration_summary },
  { key: "region_summary", label: "Region", render: (p) => p.region_summary, toString: (p) => p.region_summary },
  { key: "services_count", label: "Services by category", render: servicesByCategory, toString: (p) => String(p.services.length) },
  { key: "credits_total", label: "Credits total", render: creditsTotal, toString: (p) => String(p.credits.length) },
  { key: "access_method", label: "Access method", render: (p) => <span className="font-mono">{p.access_method}</span>, toString: (p) => p.access_method },
  { key: "geo_priority", label: "Geo priority", render: (p) => p.geo_priority, toString: (p) => p.geo_priority },
  {
    key: "use_case_tiers",
    label: "Fits tiers",
    render: (p) => (
      <div className="flex flex-wrap gap-1">
        {p.use_case_tiers.map((t) => (
          <Badge key={t} variant="default" className="text-[10px]">
            {tierLabel(t)}
          </Badge>
        ))}
      </div>
    ),
    toString: (p) => p.use_case_tiers.join(", "),
  },
  { key: "last_verified_at", label: "Last verified", render: (p) => p.last_verified_at ?? "unknown", toString: (p) => p.last_verified_at ?? "" },
  {
    key: "source",
    label: "Source",
    render: (p) => {
      const url = p.source_urls[0];
      if (!url) return "—";
      return (
        <a href={url} target="_blank" rel="noopener noreferrer" className="break-all text-accent hover:underline">
          {hostnameOf(url)}
        </a>
      );
    },
    toString: (p) => p.source_urls[0] ?? "",
  },
];
