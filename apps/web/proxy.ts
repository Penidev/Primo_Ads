import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { buildCsp, createNonce } from "@/lib/csp";

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
    return withCsp(NextResponse.redirect(login));
  }

  if (AUTH_PAGES.includes(pathname) && hasSession) {
    return withCsp(NextResponse.redirect(new URL("/dashboard", request.url)));
  }

  // The nonce has to reach Next itself, not just the browser: Next reads it from
  // the *request* CSP header and stamps it onto the script tags it generates.
  // Setting the response header alone would produce a policy that blocks the
  // framework's own hydration scripts.
  const nonce = createNonce();
  const csp = buildCsp({ nonce, isDevelopment: process.env.NODE_ENV !== "production" });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

/**
 * CSP for responses that never reach the app, so no nonce is needed.
 *
 * A redirect carries no scripts, but it does carry a Location header, and a
 * policy is still worth sending so the directives that are not script-related
 * (`frame-ancestors`, `form-action`) apply to anything a client renders.
 */
function withCsp(response: NextResponse): NextResponse {
  response.headers.set(
    "Content-Security-Policy",
    buildCsp({
      nonce: createNonce(),
      isDevelopment: process.env.NODE_ENV !== "production",
    })
  );
  return response;
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
