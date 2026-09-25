import { NextResponse, type NextRequest } from "next/server";
import { isValidSessionCookie, SESSION_COOKIE_NAME } from "@/lib/session";

/**
 * Site-wide login gate. Runs on every request except the ones excluded by
 * `config.matcher` below (Next internals, static files, favicon/icon). A
 * page request without a valid session cookie redirects to
 * `/login?next=<path>`; an `/api/*` request gets a 401 JSON body instead —
 * the browser never reaches a page or an API route without a session.
 */
export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (pathname === "/login" || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  const cookieValue = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (await isValidSessionCookie(cookieValue)) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    /*
     * Match every path except:
     * - _next/static, _next/image (Next.js internals)
     * - favicon.ico, icon.svg and other files with an extension (static assets)
     */
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|.*\\.[\\w]+$).*)",
  ],
};
