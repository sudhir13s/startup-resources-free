/**
 * Site-login session cookie — server-only, Edge-runtime-safe.
 *
 * Used by both `middleware.ts` (Edge runtime) and the `/api/auth/*` route
 * handlers, so this module uses only Web Crypto (`crypto.subtle`), never
 * `node:crypto`, which the Edge runtime does not provide.
 *
 * The cookie value is a single static derived value — not a token with an
 * expiry encoded in it — so `middleware.ts` only ever has to recompute this
 * same value and compare:
 *   ros_auth = hex HMAC-SHA256(key=RESOURCEOS_PASSWORD, msg="resourceos-login:" + RESOURCEOS_USERNAME)
 * Changing the password (or username) changes this value, so every existing
 * cookie stops matching — no revocation list needed. The raw password is
 * never stored in the cookie itself, only this derived value.
 */

export const SESSION_COOKIE_NAME = "ros_auth";
const SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30 days
const LOGIN_KEY_LABEL = "resourceos-login:";

/** Site-login credentials read from env; null when either is unset (login disabled). */
export function getSiteCredentials(): { username: string; password: string } | null {
  const username = process.env.RESOURCEOS_USERNAME?.trim();
  const password = process.env.RESOURCEOS_PASSWORD;
  if (!username || !password) return null;
  return { username, password };
}

function toHex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** The expected `ros_auth` cookie value for the currently configured
 * credentials. Null when login is unconfigured. */
export async function expectedSessionCookieValue(): Promise<string | null> {
  const creds = getSiteCredentials();
  if (!creds) return null;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(creds.password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const message = new TextEncoder().encode(`${LOGIN_KEY_LABEL}${creds.username}`);
  const signatureBytes = await crypto.subtle.sign("HMAC", key, message);
  return toHex(signatureBytes);
}

/** True when `cookieValue` matches the expected session cookie for the
 * currently configured credentials (constant-time via Web Crypto's own
 * fixed-length hex comparison — both sides compare equal-length hex
 * strings derived from a fixed-size digest). */
export async function isValidSessionCookie(cookieValue: string | undefined): Promise<boolean> {
  if (!cookieValue) return false;
  const expected = await expectedSessionCookieValue();
  if (!expected) return false;
  return timingSafeHexEqual(cookieValue, expected);
}

function timingSafeHexEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Constant-time compare of two strings via their SHA-256 digests (Web
 * Crypto — Edge-safe). Used by the login route to compare the submitted
 * username/password against the configured ones without a length- or
 * content-dependent early exit.
 */
export async function timingSafeStringEqual(a: string, b: string): Promise<boolean> {
  const [digestA, digestB] = await Promise.all([sha256(a), sha256(b)]);
  let diff = 0;
  for (let i = 0; i < digestA.length; i += 1) {
    diff |= digestA[i] ^ digestB[i];
  }
  return diff === 0;
}

async function sha256(value: string): Promise<Uint8Array> {
  const hashBuffer = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return new Uint8Array(hashBuffer);
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  };
}
