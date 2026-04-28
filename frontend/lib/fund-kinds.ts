/** Shared (server-safe) helpers for the Funds & Credits page kind filter.
 *
 * Lives outside the "use client" boundary so both the server-rendered
 * `app/funds/page.tsx` and the client `FundsSidebar` component can import
 * from here. Importing functions/constants from a "use client" module into a
 * server component yields the runtime "is not a function" error because the
 * bundler turns those exports into client-reference placeholders.
 */

/** The four canonical fund kinds. Slugs cover both singular and legacy plural
 * (e.g. "grant" + "grants") so the filter works regardless of which form the
 * backend emits. The UI shows the singular as the user-facing label. */
export const FUND_KINDS = [
  { key: "grant", label: "Grant", slugs: ["grant", "grants"] },
  {
    key: "credit",
    label: "Credit",
    slugs: ["startup-credit", "startup-credits"],
  },
  {
    key: "accelerator",
    label: "Accelerator",
    slugs: ["accelerator", "accelerators"],
  },
  { key: "perk", label: "Perk", slugs: ["perk", "perks"] },
] as const;

export type FundKind = (typeof FUND_KINDS)[number]["key"];
export type FundKindSlugs = ReadonlyArray<string>;

/** Resolve a list of selected kind keys to the full set of category slugs to
 * accept. Used by the page server component to filter the records. */
export function fundKindSlugs(keys: ReadonlyArray<string>): FundKindSlugs {
  if (keys.length === 0) return FUND_KINDS.flatMap((k) => k.slugs);
  return FUND_KINDS.filter((k) => keys.includes(k.key)).flatMap(
    (k) => k.slugs,
  );
}

/** Inverse mapping: kind-key → category slugs accepted as that kind. */
export const KIND_TO_SLUGS: Record<FundKind, ReadonlyArray<string>> = {
  grant: ["grant", "grants"],
  credit: ["startup-credit", "startup-credits"],
  accelerator: ["accelerator", "accelerators"],
  perk: ["perk", "perks"],
};
