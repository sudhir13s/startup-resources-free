import { Badge } from "@/components/ui/badge";
import { categoryLabel } from "@/lib/catalog/labels";
import type { Category } from "@/lib/types";

/** Primary category as a mono label, followed by a "+ Database, Storage…"
 * chip listing the record's other service categories (from `categories`,
 * the backend-derived superset that includes every service's category —
 * this is what makes AWS show up under Databases/Storage too). */
export function CategoryChips({
  primary,
  categories,
}: {
  primary: Category;
  categories: Category[];
}) {
  const others = categories.filter((c) => c !== primary);
  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
        {categoryLabel(primary)}
      </span>
      {others.length > 0 ? (
        <Badge variant="outline" className="text-[9px]" title={others.map(categoryLabel).join(", ")}>
          + {others.map(categoryLabel).join(", ")}
        </Badge>
      ) : null}
    </div>
  );
}
