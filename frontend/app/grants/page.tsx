import { redirect } from "next/navigation";

/**
 * `/grants` was renamed to `/funds` in Sprint #5 — funds is the broader
 * label that covers grants + cloud credits + accelerators + perks (i.e.
 * "things that GIVE you money"). This redirect preserves any pre-rename
 * bookmarks. Query params (e.g. ?region=india) flow through.
 */
export default function GrantsRedirectPage({
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
  redirect(tail ? `/funds?${tail}` : "/funds");
}
