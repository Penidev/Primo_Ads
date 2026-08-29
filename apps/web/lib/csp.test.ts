import { describe, expect, it } from "vitest";
import { buildCsp, createNonce } from "./csp";

function directives(policy: string): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const part of policy.split(";")) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (name) map.set(name, values);
  }
  return map;
}

const prod = () => buildCsp({ nonce: "TESTNONCE" });
const dev = () => buildCsp({ nonce: "TESTNONCE", isDevelopment: true });

describe("buildCsp", () => {
  it("carries the nonce in script-src", () => {
    expect(directives(prod()).get("script-src")).toContain("'nonce-TESTNONCE'");
  });

  it("uses strict-dynamic so framework chunks load without allow-listing", () => {
    expect(directives(prod()).get("script-src")).toContain("'strict-dynamic'");
  });

  // The failure mode this whole module exists to prevent. Allowing inline
  // script would also allow injected script, leaving CSP close to useless
  // against XSS.
  it("never allows inline script", () => {
    for (const policy of [prod(), dev()]) {
      expect(directives(policy).get("script-src")).not.toContain("'unsafe-inline'");
    }
  });

  it("does not allow eval in production", () => {
    expect(directives(prod()).get("script-src")).not.toContain("'unsafe-eval'");
  });

  it("allows eval only in development, for React Refresh", () => {
    expect(directives(dev()).get("script-src")).toContain("'unsafe-eval'");
  });

  it("locks down the directives that have no legitimate use here", () => {
    const d = directives(prod());
    expect(d.get("object-src")).toEqual(["'none'"]);
    expect(d.get("frame-src")).toEqual(["'none'"]);
    expect(d.get("frame-ancestors")).toEqual(["'none'"]);
    expect(d.get("base-uri")).toEqual(["'self'"]);
    expect(d.get("form-action")).toEqual(["'self'"]);
  });

  it("keeps connect-src same-origin, since the API is reached via the rewrite", () => {
    expect(directives(prod()).get("connect-src")).toEqual(["'self'"]);
  });

  it("permits the image sources the product actually renders", () => {
    const imgSrc = directives(prod()).get("img-src")!;
    // data: for the client-rendered MFA QR code, https: for provider and
    // bucket-hosted stills whose host is not known at build time.
    expect(imgSrc).toContain("data:");
    expect(imgSrc).toContain("https:");
  });

  it("upgrades insecure requests in production but not in development", () => {
    expect(directives(prod()).has("upgrade-insecure-requests")).toBe(true);
    expect(directives(dev()).has("upgrade-insecure-requests")).toBe(false);
  });

  it("always constrains default-src", () => {
    expect(directives(prod()).get("default-src")).toEqual(["'self'"]);
  });

  it("emits no empty or malformed segments", () => {
    for (const part of prod().split(";")) {
      expect(part.trim()).not.toBe("");
    }
    expect(prod()).not.toMatch(/;\s*;/);
  });
});

describe("createNonce", () => {
  it("is unique per call", () => {
    const seen = new Set(Array.from({ length: 500 }, () => createNonce()));
    expect(seen.size).toBe(500);
  });

  it("carries at least 128 bits of entropy", () => {
    // 16 random bytes -> 24 base64 characters including padding.
    expect(createNonce()).toHaveLength(24);
  });

  it("is valid base64, which the CSP token grammar requires", () => {
    for (let i = 0; i < 50; i += 1) {
      expect(createNonce()).toMatch(/^[A-Za-z0-9+/]+={0,2}$/);
    }
  });

  it("cannot break out of the policy string", () => {
    // A nonce containing a quote or semicolon would let a crafted value inject
    // directives. Base64's alphabet excludes both, and this pins that.
    for (let i = 0; i < 50; i += 1) {
      const nonce = createNonce();
      expect(nonce).not.toMatch(/['";\s]/);
    }
  });
});
