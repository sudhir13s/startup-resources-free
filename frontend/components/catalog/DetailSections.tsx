import { Badge } from "@/components/ui/badge";
import { categoryLabel, pricingLayerLabel } from "@/lib/catalog/labels";
import { formatCreditAmount, formatCreditDuration, formatLimitPeriod, formatLimitValue } from "@/lib/catalog/format";
import type { Credit, Service } from "@/lib/types";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
      {children}
    </h3>
  );
}

/** "TL;DR" — highlights as bullets. Hidden when empty. */
export function HighlightsSection({ highlights }: { highlights: string[] }) {
  if (highlights.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionHeading>TL;DR</SectionHeading>
      <ul className="flex flex-col gap-1.5 text-sm leading-relaxed text-fg-muted">
        {highlights.map((h, i) => (
          <li key={i}>• {h}</li>
        ))}
      </ul>
    </section>
  );
}

/** A single service card inside "What's free" — pricing-layer badge,
 * summary, and a Label | Value | Period limits table. */
function ServiceCard({ service }: { service: Service }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-bg-tile p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-fg">{service.name}</span>
        <Badge variant="muted">{pricingLayerLabel(service.pricing_layer)}</Badge>
      </div>
      <p className="text-sm leading-relaxed text-fg-muted">{service.summary}</p>
      {service.limits.length > 0 ? (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-fg-subtle">
              <th className="pb-1 pr-3 font-mono font-medium uppercase tracking-wider">Label</th>
              <th className="pb-1 pr-3 font-mono font-medium uppercase tracking-wider">Value</th>
              <th className="pb-1 font-mono font-medium uppercase tracking-wider">Period</th>
            </tr>
          </thead>
          <tbody>
            {service.limits.map((limit, i) => (
              <tr key={i} className="border-t border-border/60">
                <td className="py-1.5 pr-3 text-fg-muted">{limit.label}</td>
                <td className="py-1.5 pr-3 font-medium text-fg">{formatLimitValue(limit)}</td>
                <td className="py-1.5 text-fg-subtle">{formatLimitPeriod(limit) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {service.notes ? <p className="text-xs italic text-fg-subtle">{service.notes}</p> : null}
    </div>
  );
}

/** "What's free" — services grouped by their service category. */
export function ServicesSection({ services }: { services: Service[] }) {
  if (services.length === 0) return null;
  const grouped = new Map<string, Service[]>();
  for (const s of services) {
    const list = grouped.get(s.category) ?? [];
    list.push(s);
    grouped.set(s.category, list);
  }

  return (
    <section className="flex flex-col gap-3">
      <SectionHeading>What&apos;s free</SectionHeading>
      {[...grouped.entries()].map(([category, items]) => (
        <div key={category} className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold text-fg-muted">{categoryLabel(category)}</h4>
          <div className="flex flex-col gap-2">
            {items.map((s, i) => (
              <ServiceCard key={`${s.name}-${i}`} service={s} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

/** Credits table — amount (currency-aware), duration, conditions. */
export function CreditsSection({ credits }: { credits: Credit[] }) {
  if (credits.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionHeading>Credits</SectionHeading>
      <table className="w-full rounded-md border border-border bg-bg-tile text-xs">
        <thead>
          <tr className="text-left text-fg-subtle">
            <th className="p-2 font-mono font-medium uppercase tracking-wider">Label</th>
            <th className="p-2 font-mono font-medium uppercase tracking-wider">Amount</th>
            <th className="p-2 font-mono font-medium uppercase tracking-wider">Duration</th>
            <th className="p-2 font-mono font-medium uppercase tracking-wider">Conditions</th>
          </tr>
        </thead>
        <tbody>
          {credits.map((c, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="p-2 text-fg-muted">{c.label}</td>
              <td className="p-2 font-medium text-fg">{formatCreditAmount(c.amount, c.currency)}</td>
              <td className="p-2 text-fg-muted">{formatCreditDuration(c.duration_days)}</td>
              <td className="p-2 text-fg-subtle">{c.conditions ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Generic bullet-list section (After the free period / Gotchas /
 * Restrictions). Hidden when there's nothing to show. */
export function BulletSection({
  title,
  items,
}: {
  title: string;
  items: string[] | string | null;
}) {
  const list = items === null ? [] : Array.isArray(items) ? items : [items];
  if (list.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionHeading>{title}</SectionHeading>
      <ul className="flex flex-col gap-1.5 text-sm leading-relaxed text-fg-muted">
        {list.map((item, i) => (
          <li key={i}>• {item}</li>
        ))}
      </ul>
    </section>
  );
}
