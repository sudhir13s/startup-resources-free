/**
 * Admin session helpers — server-only. Never import from a Client Component.
 *
 * The admin passphrase (ADMIN_TOKEN) never reaches the browser. Login
 * compares the submitted passphrase against ADMIN_TOKEN and, on success,
 * sets an httpOnly session cookie whose value is an HMAC of ADMIN_TOKEN
 * (not the token itself) so the cookie can be verified without storing
 * the token client-side.
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const ADMIN_COOKIE_NAME = "ros_admin";
const SESSION_CONTEXT = "ros-admin-session-v1";
const COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30 days

/** Reads ADMIN_TOKEN; null when unset (refresh feature disabled). */
export function getAdminToken(): string | null {
  const token = process.env.ADMIN_TOKEN?.trim();
  return token && token.length > 0 ? token : null;
}

/** Expected session-cookie value for the configured ADMIN_TOKEN. */
export function expectedSessionValue(adminToken: string): string {
  return createHmac("sha256", adminToken).update(SESSION_CONTEXT).digest("hex");
}

/** Constant-time compare of two equal-length SHA-256 digests of the inputs. */
export function timingSafeStringEqual(a: string, b: string): boolean {
  const digestA = createHash("sha256").update(a, "utf8").digest();
  const digestB = createHash("sha256").update(b, "utf8").digest();
  return timingSafeEqual(digestA, digestB);
}

/** True when the given cookie value matches the current admin session. */
export function isValidSessionCookie(cookieValue: string | undefined): boolean {
  const adminToken = getAdminToken();
  if (!adminToken || !cookieValue) return false;
  return timingSafeStringEqual(cookieValue, expectedSessionValue(adminToken));
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    path: "/",
    maxAge: COOKIE_MAX_AGE_SECONDS,
  };
}
