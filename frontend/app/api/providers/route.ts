import { NextResponse } from "next/server";
import { backendGet } from "@/lib/api";
import type { ProviderDetailResponse, ProvidersResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

const FORWARD_LIST_KEYS = ["variant", "tier", "category", "offer_type", "geo", "min_confidence", "q"];

/**
 * Proxies `/api/providers` (list, with the catalog filters) and, when an
 * `id` query param is present, `/api/providers/{id}` (single-record
 * detail — used by ProviderDetail's client-side "related offers" fetch
 * and by CommandPalette search results).
 */
export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const id = incoming.searchParams.get("id");

  if (id) {
    const result = await backendGet<ProviderDetailResponse>(`/api/providers/${encodeURIComponent(id)}`);
    if (!result.ok) {
      return NextResponse.json({ error: result.detail }, { status: result.status || 502 });
    }
    return NextResponse.json(result.data);
  }

  const query: Record<string, string[]> = {};
  for (const key of FORWARD_LIST_KEYS) {
    const values = incoming.searchParams.getAll(key);
    if (values.length > 0) query[key] = values;
  }

  const result = await backendGet<ProvidersResponse>("/api/providers", query);
  if (!result.ok) {
    return NextResponse.json({ error: result.detail }, { status: result.status || 502 });
  }
  return NextResponse.json(result.data);
}
