import { NextResponse } from "next/server";
import type { ProvidersResponse } from "@/lib/utils";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const upstream = new URL("/api/providers", BACKEND_URL);
  incoming.searchParams.forEach((value, key) =>
    upstream.searchParams.set(key, value)
  );

  try {
    const res = await fetch(upstream.toString(), {
      headers: { accept: "application/json" },
      cache: "no-store",
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "upstream_error", status: res.status },
        { status: 502 }
      );
    }

    const data = (await res.json()) as ProvidersResponse;
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json(
      {
        error: "upstream_unreachable",
        backend_url: BACKEND_URL,
        detail: e instanceof Error ? e.message : String(e),
      },
      { status: 502 }
    );
  }
}
