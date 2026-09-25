import { SectionTitle, FilterCheckboxRow } from "@/components/catalog/filters/shared";
import { categoryLabel } from "@/lib/catalog/labels";
import type { Facets } from "@/lib/types";

export function CategoryFilter({
  categories,
  selected,
  facets,
  onToggle,
}: {
  categories: readonly string[];
  selected: Set<string>;
  facets: Facets | null;
  onToggle: (category: string) => void;
}) {
  return (
    <section>
      <SectionTitle>Category</SectionTitle>
      <div className="flex flex-col gap-1.5">
        {categories.map((c) => {
          const checked = selected.has(c);
          const count = facets?.categories[c] ?? 0;
          return (
            <FilterCheckboxRow
              key={c}
              checked={checked}
              disabled={!checked && facets !== null && count === 0}
              label={categoryLabel(c)}
              count={count}
              onToggle={() => onToggle(c)}
            />
          );
        })}
      </div>
    </section>
  );
}
