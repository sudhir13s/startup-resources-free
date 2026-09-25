import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { ADMIN_COOKIE_NAME, getAdminToken, isValidSessionCookie } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET() {
  const configured = getAdminToken() !== null;
  const cookieValue = cookies().get(ADMIN_COOKIE_NAME)?.value;
  const authenticated = configured && isValidSessionCookie(cookieValue);
  return NextResponse.json({ authenticated, configured });
}
