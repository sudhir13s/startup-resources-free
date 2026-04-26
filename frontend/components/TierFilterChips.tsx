"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import {
  TIERS,
  TIER_LABELS,
  TIER_DESCRIPTIONS,
  type Tier,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

const TIER_ACCENT: Record<Tier, string> = {
  hobby: "data-[active=true]:border-tier-hobby data-[active=true]:bg-tier-hobby/10 data-[active=true]:text-tier-hobby",
  personal:
    "data-[active=true]:border-tier-personal data-[active=true]:bg-tier-personal/10 data-[active=true]:text-tier-personal",
  "startup-mvp":
    "data-[active=true]:border-tier-mvp data-[active=true]:bg-tier-mvp/10 data-[active=true]:text-tier-mvp",
  startup:
    "data-[active=true]:border-tier-startup data-[active=true]:bg-tier-startup/10 data-[active=true]:text-tier-startup",
};

export function TierFilterChips({
  current,
  counts,
}: {
  current: Tier;
  counts: Record<Tier, number>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const onPick = useCallback(
    (tier: Tier) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tier", tier);
      router.push(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  return (
    <div
      role="radiogroup"
      aria-label="Filter by project stage"
      className="-mx-4 flex gap-2 overflow-x-auto px-4 py-2 sm:mx-0 sm:flex-wrap sm:px-0"
    >
      {TIERS.map((tier) => {
        const active = tier === current;
        return (
          <button
            key={tier}
            type="button"
            role="radio"
            aria-checked={active}
            data-active={active}
            onClick={() => onPick(tier)}
            className={cn(
              "group flex shrink-0 flex-col items-start rounded-xl border border-bg-subtle bg-bg-surface/60 px-4 py-3 text-left transition-all hover:border-bg-subtle/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base",
              "data-[active=true]:bg-bg-surface",
              TIER_ACCENT[tier]
            )}
          >
            <div className="flex items-baseline gap-2">
              <span className="text-base font-semibold">
                {TIER_LABELS[tier]}
              </span>
              <span className="font-mono text-xs text-white/60">
                {counts[tier]}
              </span>
            </div>
            <span className="mt-1 text-xs text-white/60 group-hover:text-white/80 group-data-[active=true]:text-white/80">
              {TIER_DESCRIPTIONS[tier]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
