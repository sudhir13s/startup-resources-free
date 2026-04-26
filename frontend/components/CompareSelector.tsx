"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Provider } from "@/lib/utils";
import { cn } from "@/lib/utils";

const MAX_PINS = 6;

export function CompareSelector({
  allProviders,
  pinnedIds,
}: {
  allProviders: Provider[];
  pinnedIds: string[];
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [openPicker, setOpenPicker] = useState(false);
  const pinnedSet = useMemo(() => new Set(pinnedIds), [pinnedIds]);

  const update = useCallback(
    (next: string[]) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next.length === 0) params.delete("ids");
      else params.set("ids", next.join(","));
      router.push(`/compare?${params.toString()}`);
    },
    [router, searchParams]
  );

  const remove = (id: string) => update(pinnedIds.filter((x) => x !== id));
  const add = (id: string) => {
    if (pinnedIds.includes(id)) return;
    if (pinnedIds.length >= MAX_PINS) return;
    update([...pinnedIds, id]);
    setOpenPicker(false);
  };

  const available = allProviders.filter((p) => !pinnedSet.has(p.id));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {pinnedIds.length === 0 ? (
          <span className="text-sm text-fg-muted">
            No providers pinned yet. Pick up to {MAX_PINS}.
          </span>
        ) : (
          pinnedIds.map((id) => {
            const p = allProviders.find((x) => x.id === id);
            return (
              <Badge
                key={id}
                variant="default"
                className="gap-1 px-2 py-1 text-xs"
              >
                {p ? p.name : id}
                <button
                  type="button"
                  onClick={() => remove(id)}
                  aria-label={`Remove ${p?.name ?? id} from comparison`}
                  className="ml-1 rounded p-0.5 hover:bg-bg-subtle"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            );
          })
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpenPicker((v) => !v)}
          disabled={pinnedIds.length >= MAX_PINS}
          aria-haspopup="listbox"
          aria-expanded={openPicker}
        >
          <Plus className="h-3 w-3" />
          {pinnedIds.length === 0 ? "Add provider" : "Add more"}
        </Button>
        {pinnedIds.length > 0 ? (
          <Button variant="ghost" size="sm" onClick={() => update([])}>
            Clear
          </Button>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-fg-subtle">
          {pinnedIds.length} / {MAX_PINS} pinned
        </span>
      </div>

      {openPicker ? (
        <div className="rounded-lg border border-border bg-bg-surface p-3">
          <ul
            role="listbox"
            aria-label="Available providers"
            className="grid max-h-72 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3"
          >
            {available.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => add(p.id)}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md px-3 py-2 text-left text-xs",
                    "hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  )}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-border bg-bg-tile font-mono text-xs font-semibold text-fg-muted">
                    {p.name.charAt(0)}
                  </span>
                  <span className="flex flex-col gap-0.5">
                    <span className="font-medium text-fg">{p.name}</span>
                    <span className="font-mono text-[9px] uppercase tracking-wider text-fg-subtle">
                      {p.category}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
