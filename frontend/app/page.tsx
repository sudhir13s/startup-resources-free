import { redirect } from "next/navigation";

/**
 * Root path now redirects to /resources (the canonical "things you USE"
 * view). Sprint #5 split the v0.1 catalog into two top-level views:
 *   /resources — cloud / GPU / DB / LLM-API / storage / …
 *   /funds     — grants / credits / accelerators / perks
 *
 * Search params are forwarded through the redirect so the Sidebar
 * (which calls `router.push('/?...')`) still lands users on the right
 * filtered view.
 */
export default function RootPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}): never {
  const qs = new URLSearchParams();
  if (searchParams) {
    for (const [k, v] of Object.entries(searchParams)) {
      if (v === undefined) continue;
      if (Array.isArray(v)) {
        for (const one of v) qs.append(k, one);
      } else {
        qs.set(k, v);
      }
    }
  }
  const tail = qs.toString();
  redirect(tail ? `/resources?${tail}` : "/resources");
}
