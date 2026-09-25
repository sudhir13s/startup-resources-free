import { NextResponse } from "next/server";
import { backendAuthHeader, isBackendConfigured } from "@/lib/admin";
import { backendUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Starts a backend refresh run. No separate admin check here: `middleware.ts`
 * already requires a valid site-login session on every `/api/*` request, so
 * reaching this handler means the caller is logged in.
 */
export async function POST(request: Request) {
  if (!isBackendConfigured()) {
    return NextResponse.json({ detail: "Refresh is not configured" }, { status: 503 });
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  try {
    const res = await fetch(backendUrl("/api/refresh"), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...backendAuthHeader(),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { detail: `Backend unreachable: ${String(error)}` },
      { status: 502 },
    );
  }
}
