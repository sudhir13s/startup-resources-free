"use client";

import { ResourceCard } from "@/components/ResourceCard";
import { FundCard } from "@/components/FundCard";
import { providerCardVariant, type Provider } from "@/lib/utils";

/**
 * Thin variant-router introduced in Sprint #5.
 *
 * The v0.1 dashboard had a single ProviderCard for all categories.
 * Closing CRITICAL #5 from the 2026-04-28 roundtable, we now split:
 *   - ResourceCard — things you USE (cloud / GPU / DB / AI APIs / …)
 *   - FundCard     — things that GIVE you money (grants / credits /
 *                    accelerators / perks)
 *
 * The two card schemas surface category-appropriate stat tiles, badges,
 * and call-to-action copy. The router (this file) keeps existing
 * imports of `ProviderCard` working — no callers need changes.
 */
export function ProviderCard({ provider }: { provider: Provider }) {
  const variant = providerCardVariant(provider);
  return variant === "funds" ? (
    <FundCard provider={provider} />
  ) : (
    <ResourceCard provider={provider} />
  );
}
