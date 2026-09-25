import { NextResponse } from "next/server";
import {
  ADMIN_COOKIE_NAME,
  expectedSessionValue,
  getAdminToken,
  sessionCookieOptions,
  timingSafeStringEqual,
} from "@/lib/admin";

export const dynamic = "force-dynamic";

const FAILURE_DELAY_MS = 400;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function POST(request: Request) {
  const adminToken = getAdminToken();
  if (!adminToken) {
    return NextResponse.json({ detail: "Refresh is not configured" }, { status: 503 });
  }

  let passphrase: unknown;
  try {
    const body = (await request.json()) as { passphrase?: unknown };
    passphrase = body.passphrase;
  } catch {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Invalid request body" }, { status: 401 });
  }

  if (typeof passphrase !== "string" || passphrase.length === 0) {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Passphrase required" }, { status: 401 });
  }

  if (!timingSafeStringEqual(passphrase, adminToken)) {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Incorrect passphrase" }, { status: 401 });
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(ADMIN_COOKIE_NAME, expectedSessionValue(adminToken), sessionCookieOptions());
  return response;
}
