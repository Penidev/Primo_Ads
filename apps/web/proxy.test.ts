import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { proxy } from "./proxy";

/** Build a request, optionally carrying session cookies. */
function request(
  path: string,
  cookies: Record<string, string> = {}
): NextRequest {
  const req = new NextRequest(new URL(path, "https://app.test"));
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

const SESSION = { access_token: "a.b.c" };

describe("proxy route gate", () => {
  it("redirects anonymous users away from protected areas", () => {
    for (const path of [
      "/dashboard",
      "/dashboard/projects",
      "/admin",
      "/admin/pricing",
      "/onboarding",
    ]) {
      const res = proxy(request(path));
      expect(res.status).toBe(307);
      const location = new URL(res.headers.get("location")!);
      expect(location.pathname).toBe("/login");
      // The intended destination must survive the round trip.
      expect(location.searchParams.get("next")).toBe(path);
    }
  });

  it("preserves the query string in the next parameter", () => {
    const res = proxy(request("/dashboard/projects?page=2"));
    const location = new URL(res.headers.get("location")!);
    expect(location.searchParams.get("next")).toBe("/dashboard/projects?page=2");
  });

  it("lets authenticated users through", () => {
    const res = proxy(request("/dashboard", SESSION));
    expect(res.headers.get("location")).toBeNull();
  });

  it("accepts a refresh cookie alone, since the access token may have expired", () => {
    const res = proxy(request("/dashboard", { refresh_token: "r" }));
    expect(res.headers.get("location")).toBeNull();
  });

  it("sends signed-in users away from login and register", () => {
    for (const path of ["/login", "/register"]) {
      const res = proxy(request(path, SESSION));
      expect(res.status).toBe(307);
      expect(new URL(res.headers.get("location")!).pathname).toBe("/dashboard");
    }
  });

  it("leaves public pages alone", () => {
    for (const path of ["/", "/pricing", "/login", "/forgot-password"]) {
      const res = proxy(request(path));
      expect(res.headers.get("location")).toBeNull();
    }
  });

  it("keeps password reset reachable while signed in", () => {
    // A user mid-reset may still hold a stale session; blocking them would
    // strand anyone whose password was compromised.
    for (const path of ["/forgot-password", "/reset-password"]) {
      const res = proxy(request(path, SESSION));
      expect(res.headers.get("location")).toBeNull();
    }
  });

  it("does not treat lookalike prefixes as protected", () => {
    // `/admin-guide` must not match the `/admin` prefix.
    const res = proxy(request("/admin-guide"));
    expect(res.headers.get("location")).toBeNull();
  });
});
