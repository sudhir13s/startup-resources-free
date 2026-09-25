import { NextResponse } from "next/server";
import {
  expectedSessionCookieValue,
  getSiteCredentials,
  sessionCookieOptions,
  SESSION_COOKIE_NAME,
  timingSafeStringEqual,
} from "@/lib/session";

export const dynamic = "force-dynamic";

const FAILURE_DELAY_MS = 500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function POST(request: Request) {
  const credentials = getSiteCredentials();
  if (!credentials) {
    return NextResponse.json({ detail: "Login is not configured" }, { status: 503 });
  }

  let username: unknown;
  let password: unknown;
  try {
    const body = (await request.json()) as { username?: unknown; password?: unknown };
    username = body.username;
    password = body.password;
  } catch {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Invalid request body" }, { status: 401 });
  }

  if (typeof username !== "string" || typeof password !== "string" || !username || !password) {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Username and password required" }, { status: 401 });
  }

  const [usernameMatches, passwordMatches] = await Promise.all([
    timingSafeStringEqual(username, credentials.username),
    timingSafeStringEqual(password, credentials.password),
  ]);

  if (!usernameMatches || !passwordMatches) {
    await delay(FAILURE_DELAY_MS);
    return NextResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
  }

  const cookieValue = await expectedSessionCookieValue();
  if (!cookieValue) {
    return NextResponse.json({ detail: "Login is not configured" }, { status: 503 });
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(SESSION_COOKIE_NAME, cookieValue, sessionCookieOptions());
  return response;
}
