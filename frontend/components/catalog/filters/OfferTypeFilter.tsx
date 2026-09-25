import { SectionTitle, FilterCheckboxRow } from "@/components/catalog/filters/shared";
import { OFFER_TYPES, offerTypeLabel } from "@/lib/catalog/labels";
import type { Facets, OfferType } from "@/lib/types";

export function OfferTypeFilter({
  selected,
  facets,
  onToggle,
}: {
  selected: Set<string>;
  facets: Facets | null;
  onToggle: (offerType: OfferType) => void;
}) {
  return (
    <section>
      <SectionTitle>Offer type</SectionTitle>
      <div className="flex flex-col gap-1.5">
        {OFFER_TYPES.map((o) => (
          <FilterCheckboxRow
            key={o}
            checked={selected.has(o)}
            label={offerTypeLabel(o)}
            count={facets?.offer_types[o] ?? 0}
            onToggle={() => onToggle(o)}
          />
        ))}
      </div>
    </section>
  );
}
