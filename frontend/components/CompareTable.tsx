import { cn } from "@/lib/utils";
import { COMPARE_ROWS } from "@/components/catalog/compareRows";
import type { ProviderRecord } from "@/lib/types";

export function CompareTable({ providers }: { providers: ProviderRecord[] }) {
  if (providers.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-bg-surface p-12 text-center">
        <p className="text-sm text-fg-muted">Pick at least 2 providers to compare side-by-side.</p>
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
              <th key={p.provider_id} scope="col" className="min-w-[200px] border-b border-border px-3 py-2 text-left font-semibold text-fg">
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
          {COMPARE_ROWS.map((r) => {
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
                      key={p.provider_id}
                      className={cn("border-b border-border px-3 py-3 align-top text-xs", differs && "bg-warn/10", !differs && "text-fg-muted")}
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
