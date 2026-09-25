import { SectionTitle, FilterCheckboxRow } from "@/components/catalog/filters/shared";
import { DEFAULT_VISIBLE_GEO, EXPANDABLE_GEO, geoPriorityLabel } from "@/lib/catalog/labels";
import type { Facets, GeoPriority } from "@/lib/types";

export function RegionFilter({
  selected,
  facets,
  showAll,
  onToggle,
  onToggleShowAll,
}: {
  selected: Set<string>;
  facets: Facets | null;
  showAll: boolean;
  onToggle: (geo: GeoPriority) => void;
  onToggleShowAll: (show: boolean) => void;
}) {
  return (
    <section>
      <SectionTitle>Region</SectionTitle>
      <div className="flex flex-col gap-1.5">
        {DEFAULT_VISIBLE_GEO.map((g) => (
          <FilterCheckboxRow
            key={g}
            checked={selected.has(g)}
            label={geoPriorityLabel(g)}
            count={facets?.geo[g] ?? 0}
            onToggle={() => onToggle(g)}
          />
        ))}
        <button
          type="button"
          onClick={() => onToggleShowAll(!showAll)}
          className="mt-1 text-left text-xs text-accent hover:underline"
        >
          {showAll ? "Hide US / EU / other-region-only" : "Show US / EU / other-region-only"}
        </button>
        {showAll
          ? EXPANDABLE_GEO.map((g) => (
              <FilterCheckboxRow
                key={g}
                checked={selected.has(g)}
                label={geoPriorityLabel(g)}
                count={facets?.geo[g] ?? 0}
                onToggle={() => onToggle(g)}
              />
            ))
          : null}
      </div>
    </section>
  );
}
