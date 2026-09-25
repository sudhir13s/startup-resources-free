"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Search } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { categoryLabel, tierLabel } from "@/lib/catalog/labels";
import type { ProviderRecord, ProvidersResponse } from "@/lib/types";

const NAV_ITEMS = [
  { label: "Resources", href: "/resources" },
  { label: "Compare", href: "/compare" },
  { label: "Funds & Credits", href: "/funds" },
  { label: "Changes", href: "/changes" },
  { label: "Free-LLM Chain", href: "/freellm" },
  { label: "Media Benchmark", href: "/media-benchmark" },
] as const;

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<ProviderRecord[]>([]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    const onCustom = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-command-palette", onCustom as EventListener);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-command-palette", onCustom as EventListener);
    };
  }, []);

  // Debounced search via the providers proxy — `q=` is forwarded to the
  // backend's full-text filter.
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      const url = query.trim() ? `/api/providers?q=${encodeURIComponent(query.trim())}` : "/api/providers";
      fetch(url, { signal: ctrl.signal })
        .then((r) => (r.ok ? r.json() : null))
        .then((data: ProvidersResponse | null) => {
          if (data) setProviders(data.items);
        })
        .catch(() => {});
    }, 150);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [open, query]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent side="center" className="max-w-xl gap-0 p-0 sm:max-w-2xl">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <Command
          label="Global command palette"
          loop
          shouldFilter={false}
          className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1"
        >
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <Search className="h-4 w-4 text-fg-subtle" />
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder='Try "free postgres 10gb" or "AI inference for India"…'
              className="h-8 w-full bg-transparent text-sm text-fg outline-none placeholder:text-fg-subtle"
            />
            <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle">
              Esc
            </kbd>
          </div>
          <Command.List className="max-h-[400px] overflow-y-auto p-1">
            <Command.Empty className="px-3 py-6 text-center text-sm text-fg-muted">No matches.</Command.Empty>
            {!query ? (
              <Command.Group heading="Navigate">
                {NAV_ITEMS.map((n) => (
                  <Command.Item
                    key={n.href}
                    value={`nav-${n.label}`}
                    onSelect={() => go(n.href)}
                    className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-fg aria-selected:bg-bg-tile"
                  >
                    <span className="font-mono text-[10px] uppercase text-fg-subtle">Page</span>
                    <span>{n.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
            {providers.length > 0 ? (
              <Command.Group heading={`Providers (${providers.length})`}>
                {providers.map((p) => (
                  <Command.Item
                    key={p.provider_id}
                    value={p.provider_id}
                    onSelect={() => go(p.card_variant === "funds" ? `/funds?focus=${p.provider_id}` : `/resources?focus=${p.provider_id}`)}
                    className="flex cursor-pointer flex-col gap-0.5 rounded px-3 py-2 text-sm aria-selected:bg-bg-tile"
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="font-medium text-fg">{p.name}</span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                        {categoryLabel(p.category)}
                      </span>
                      {p.india_accessible ? <span className="font-mono text-[10px] text-india">IN</span> : null}
                    </div>
                    <span className="truncate text-xs text-fg-muted">{p.headline}</span>
                    <span className="font-mono text-[9px] text-fg-subtle">
                      {p.use_case_tiers.map(tierLabel).join(" · ")}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
          </Command.List>
          <div className="flex items-center justify-between border-t border-border px-3 py-2 font-mono text-[10px] text-fg-subtle">
            <span>
              <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5">↑↓</kbd> navigate
            </span>
            <span>
              <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5">↵</kbd> open
            </span>
            <span>
              <kbd className="rounded border border-border bg-bg-tile px-1.5 py-0.5">⌘K</kbd> toggle
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
