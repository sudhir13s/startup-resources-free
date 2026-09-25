import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ADMIN_COOKIE_NAME, getAdminToken, isValidSessionCookie } from "@/lib/admin";
import { backendUrl } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const adminToken = getAdminToken();
  if (!adminToken) {
    return NextResponse.json({ detail: "Refresh is not configured" }, { status: 503 });
  }

  const cookieValue = cookies().get(ADMIN_COOKIE_NAME)?.value;
  if (!isValidSessionCookie(cookieValue)) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
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
        "X-ResourceOS-Passphrase": adminToken,
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
