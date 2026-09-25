import { NextResponse } from "next/server";
import { backendAuthHeader, isBackendConfigured } from "@/lib/admin";
import { backendUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

const ALLOWED_ACTIONS = new Set(["approve", "reject"]);
// candidate_id format: opaque slug/uuid-ish token — letters, digits, dash, underscore.
const CANDIDATE_ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

/**
 * Approves/rejects a discovered candidate. No separate admin check here:
 * `middleware.ts` already requires a valid site-login session on every
 * `/api/*` request, so reaching this handler means the caller is logged in.
 */
export async function POST(
  _request: Request,
  { params }: { params: { id: string; action: string } },
) {
  if (!isBackendConfigured()) {
    return NextResponse.json({ detail: "Refresh is not configured" }, { status: 503 });
  }

  const { id, action } = params;
  if (!CANDIDATE_ID_PATTERN.test(id)) {
    return NextResponse.json({ detail: "Invalid candidate id" }, { status: 400 });
  }
  if (!ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ detail: "Invalid action" }, { status: 400 });
  }

  try {
    const res = await fetch(backendUrl(`/api/candidates/${id}/${action}`), {
      method: "POST",
      headers: backendAuthHeader(),
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
