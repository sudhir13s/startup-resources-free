import { cn } from "@/lib/utils";

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
      {children}
    </h3>
  );
}

export function FilterCheckboxRow({
  checked,
  disabled,
  label,
  count,
  onToggle,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  count: number;
  onToggle: () => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 text-sm text-fg-muted hover:text-fg",
        disabled && "cursor-not-allowed opacity-40"
      )}
    >
      <span className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={onToggle}
          className="h-3.5 w-3.5 rounded border-border-strong text-accent focus:ring-accent"
        />
        {label}
      </span>
      <span className="font-mono text-[10px] text-fg-subtle">{count}</span>
    </label>
  );
}

export function FilterRadioRow({
  active,
  label,
  count,
  onSelect,
}: {
  active: boolean;
  label: string;
  count?: number;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onSelect}
      className={cn(
        "group flex items-center justify-between rounded-md px-3 py-1.5 text-sm transition-colors",
        "hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        active && "bg-bg-tile text-accent"
      )}
    >
      <span className="flex items-center gap-2">
        <span className={cn("h-1.5 w-1.5 rounded-full", active ? "bg-accent" : "bg-border-strong")} />
        {label}
      </span>
      {count !== undefined ? (
        <span className={cn("font-mono text-xs", active ? "text-accent" : "text-fg-subtle")}>{count}</span>
      ) : null}
    </button>
  );
}
