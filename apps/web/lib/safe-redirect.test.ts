import { describe, expect, it } from "vitest";
import { DEFAULT_REDIRECT, safeRedirect } from "./safe-redirect";

describe("safeRedirect", () => {
  it("keeps same-site paths", () => {
    expect(safeRedirect("/dashboard/projects")).toBe("/dashboard/projects");
    expect(safeRedirect("/admin/pricing?tab=credits")).toBe(
      "/admin/pricing?tab=credits"
    );
    expect(safeRedirect("/dashboard#section")).toBe("/dashboard#section");
  });

  it("falls back when no target is supplied", () => {
    expect(safeRedirect(null)).toBe(DEFAULT_REDIRECT);
    expect(safeRedirect(undefined)).toBe(DEFAULT_REDIRECT);
    expect(safeRedirect("")).toBe(DEFAULT_REDIRECT);
  });

  // Each of these is a real open-redirect technique, not a hypothetical.
  it.each([
    ["absolute http url", "https://evil.test/login"],
    ["absolute url, no scheme case", "HTTPS://evil.test"],
    ["protocol-relative", "//evil.test"],
    ["protocol-relative with path", "//evil.test/login"],
    ["backslash protocol-relative", "/\\evil.test"],
    ["double backslash", "\\\\evil.test"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,<script>alert(1)</script>"],
    ["relative path", "dashboard"],
    ["newline smuggling", "/dashboard\nSet-Cookie: x=1"],
    ["tab smuggling", "/\tevil.test"],
    ["null byte", "/dashboard\u0000"],
  ])("rejects %s", (_label, input) => {
    expect(safeRedirect(input)).toBe(DEFAULT_REDIRECT);
  });

  it("honours a custom fallback", () => {
    expect(safeRedirect("https://evil.test", "/login")).toBe("/login");
  });

  it("never returns a value that leaves the origin", () => {
    const attempts = [
      "//evil.test",
      "/\\evil.test",
      "https://evil.test",
      "\\/evil.test",
    ];
    for (const attempt of attempts) {
      const result = safeRedirect(attempt);
      // A safe result is always a single-slash absolute path.
      expect(result.startsWith("/")).toBe(true);
      expect(result.startsWith("//")).toBe(false);
      expect(new URL(result, "https://app.test").origin).toBe("https://app.test");
    }
  });
});
