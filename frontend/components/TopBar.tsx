"use client";

import { Search } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { RefreshButton } from "@/components/refresh/RefreshButton";
import { LogoutButton } from "@/components/auth/LogoutButton";

export function TopBar() {
  return (
    <header
      role="banner"
      className="sticky top-0 z-30 flex flex-wrap items-center gap-3 border-b border-border bg-bg-base/90 px-4 py-3 backdrop-blur sm:flex-nowrap sm:gap-4 sm:px-6"
    >
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent text-base font-bold text-accent-fg">
          R
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight text-fg">
            ResourceOS
          </span>
          <span className="font-mono text-[10px] text-fg-subtle">
            v2 · catalog
          </span>
        </div>
      </div>

      <div className="order-last flex w-full items-center sm:order-none sm:flex-1 sm:max-w-md">
        <button
          type="button"
          onClick={() =>
            window.dispatchEvent(new CustomEvent("open-command-palette"))
          }
          aria-label='Open search ("⌘K")'
          aria-haspopup="dialog"
          className="relative flex h-9 w-full items-center rounded-md border border-border bg-bg-surface pl-9 pr-12 text-left text-xs text-fg-subtle hover:bg-bg-tile focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
          <span className="truncate">
            Try &quot;free postgres 10gb&quot; or &quot;AI inference for India&quot;
          </span>
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-bg-tile px-1.5 py-0.5 font-mono text-[10px] text-fg-subtle sm:inline">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="ml-auto flex items-center gap-2 shrink-0">
        <RefreshButton />
        <ThemeToggle />
        <LogoutButton />
      </div>
    </header>
  );
}
