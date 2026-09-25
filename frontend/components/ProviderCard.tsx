"use client";

import { ResourceCard } from "@/components/ResourceCard";
import { FundCard } from "@/components/FundCard";
import type { ProviderRecord } from "@/lib/types";

/** Thin variant-router: picks ResourceCard vs FundCard by `card_variant`.
 * Kept as a stable import point for callers that don't know the variant
 * ahead of time (e.g. CommandPalette results, Compare selector). */
export function ProviderCard({ provider }: { provider: ProviderRecord }) {
  return provider.card_variant === "funds" ? (
    <FundCard provider={provider} />
  ) : (
    <ResourceCard provider={provider} />
  );
}
