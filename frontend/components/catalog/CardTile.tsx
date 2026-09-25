/** Compact stat tile shared by ResourceCard and FundCard. */
export function CardTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-border bg-bg-tile px-2 py-1.5">
      <span className="font-mono text-[9px] font-semibold uppercase leading-none tracking-wider text-fg-subtle">
        {label}
      </span>
      <span className="truncate text-[11px] font-medium leading-tight text-fg" title={value}>
        {value}
      </span>
    </div>
  );
}
