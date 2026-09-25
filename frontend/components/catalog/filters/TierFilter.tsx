import { SectionTitle, FilterRadioRow } from "@/components/catalog/filters/shared";
import { TIERS, tierLabel } from "@/lib/catalog/labels";
import type { Facets, UseCaseTier } from "@/lib/types";

export function TierFilter({
  selected,
  facets,
  onSelect,
  onClear,
}: {
  selected: Set<string>;
  facets: Facets | null;
  onSelect: (tier: UseCaseTier) => void;
  onClear: () => void;
}) {
  return (
    <section>
      <SectionTitle>Project tier</SectionTitle>
      <div role="radiogroup" aria-label="Project tier" className="flex flex-col gap-1">
        <FilterRadioRow active={selected.size === 0} label="All" onSelect={onClear} />
        {TIERS.map((t) => (
          <FilterRadioRow
            key={t}
            active={selected.has(t)}
            label={tierLabel(t)}
            count={facets?.tiers[t] ?? 0}
            onSelect={() => onSelect(t)}
          />
        ))}
      </div>
    </section>
  );
}
