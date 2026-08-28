import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route gate for authenticated areas.
 *
 * Next.js 16 renamed the `middleware` file convention to `proxy`, and the
 * exported function from `middleware` to `proxy`. The old names are simply not
 * picked up — no error, no warning, the gate just stops running — so this file
 * and its export must keep these names.
 *
 * This is a **UX guard, not a security boundary.** It only checks for the
 * presence of an auth cookie so an unauthenticated visitor gets a clean redirect
 * to the login page instead of a dashboard shell full of failed requests.
 *
 * It deliberately does not verify the token or inspect claims:
 *   - the JWT secret belongs on the server, not in the proxy layer,
 *   - a forged cookie would still fail every API call, because the backend
 *     verifies the token and re-checks ownership on every request.
 *
 * Admin authorisation is likewise enforced server-side (`get_current_admin`
 * returns 404 to non-admins). Nothing here is load-bearing for access control.
 */

const ACCESS_COOKIE = "access_token";
const REFRESH_COOKIE = "refresh_token";

// Areas that require a session.
const PROTECTED_PREFIXES = ["/dashboard", "/admin", "/onboarding"];

// Pages that make no sense once signed in.
const AUTH_PAGES = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // A refresh cookie alone is enough: the access token may have expired, and the
  // client can silently rotate it. Redirecting in that case would be wrong.
  const hasSession =
    request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (isProtected && !hasSession) {
    const login = new URL("/login", request.url);
    // Preserve the destination so the user lands where they intended.
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  if (AUTH_PAGES.includes(pathname) && hasSession) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  /**
   * Skip static assets, image optimisation, and the API proxy.
   *
   * The proxy exclusion matters: API responses must return their real status
   * codes (401 in particular, which the client uses to trigger a token refresh)
   * rather than being redirected to an HTML login page.
   */
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)",
  ],
};
