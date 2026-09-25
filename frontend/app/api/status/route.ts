import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/api";
import type { RefreshStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(backendUrl("/api/refresh/status"), { cache: "no-store" });
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      return NextResponse.json({ detail }, { status: res.status });
    }
    const data = (await res.json()) as RefreshStatus;
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: `Backend unreachable: ${String(error)}` },
      { status: 502 },
    );
  }
}
