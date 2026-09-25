import { SectionTitle } from "@/components/catalog/filters/shared";
import { cn } from "@/lib/utils";
import type { ParseConfidence } from "@/lib/types";

const LEVELS: { value: ParseConfidence; label: string }[] = [
  { value: "medium", label: "Medium+" },
  { value: "high", label: "High" },
];

export function ConfidenceFilter({
  value,
  onSelect,
}: {
  value: ParseConfidence | null;
  onSelect: (confidence: ParseConfidence | null) => void;
}) {
  return (
    <section>
      <SectionTitle>Confidence</SectionTitle>
      <div role="radiogroup" aria-label="Minimum parse confidence" className="grid grid-cols-3 gap-1">
        <button
          type="button"
          role="radio"
          aria-checked={value === null}
          onClick={() => onSelect(null)}
          className={cn(
            "rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
            value === null
              ? "border-accent bg-accent/10 text-accent"
              : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile"
          )}
        >
          All
        </button>
        {LEVELS.map(({ value: level, label }) => {
          const active = level === value;
          return (
            <button
              key={level}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onSelect(active ? null : level)}
              className={cn(
                "rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-bg-surface text-fg-muted hover:bg-bg-tile"
              )}
            >
              {label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
