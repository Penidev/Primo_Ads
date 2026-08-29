/**
 * Content Security Policy.
 *
 * Kept out of `proxy.ts` so the policy itself can be tested rather than only
 * observed in a browser.
 *
 * The policy is nonce-based with `strict-dynamic` rather than
 * `script-src 'unsafe-inline'`. That distinction is the whole point: Next.js
 * emits inline scripts to carry hydration data, and the usual workaround of
 * allowing all inline script also allows any script an attacker manages to
 * inject, which leaves CSP providing close to nothing against XSS.
 *
 * `strict-dynamic` is what makes the nonce workable here: Next loads its chunks
 * from scripts that already carry the nonce, and `strict-dynamic` extends trust
 * to what those scripts load, so individual chunk URLs need no allow-listing.
 *
 * Cost, stated plainly: a per-request nonce means HTML cannot be statically
 * prerendered, so routes carrying it render on demand. For an authenticated
 * product that is largely the case anyway, and correctness of the script policy
 * is worth more than cached HTML on the marketing pages.
 */

export interface CspOptions {
  nonce: string;
  /** Development needs `unsafe-eval` for React Refresh; production must not have it. */
  isDevelopment?: boolean;
}

export function buildCsp({ nonce, isDevelopment = false }: CspOptions): string {
  const scriptSrc = [
    "'self'",
    `'nonce-${nonce}'`,
    "'strict-dynamic'",
    // React Refresh compiles components at runtime. Dev only — shipping this
    // would undo most of the benefit of the nonce.
    isDevelopment ? "'unsafe-eval'" : null,
  ].filter(Boolean);

  const directives: Record<string, string[] | null> = {
    "default-src": ["'self'"],
    "script-src": scriptSrc as string[],

    // Inline style is permitted deliberately. Next injects critical CSS inline,
    // and unlike script, injected CSS cannot execute. The residual risk is
    // defacement and some exfiltration via selectors, which is not worth
    // breaking rendering over.
    "style-src": ["'self'", "'unsafe-inline'"],

    // `data:` covers the MFA QR code, which is rendered client-side to a data
    // URI so the provisioning secret never travels as a separate fetchable URL.
    // `https:` covers generated stills, whose host depends on the storage bucket
    // and video provider CDN and so is not knowable at build time. Broad, but an
    // image cannot execute.
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "media-src": ["'self'", "blob:", "https:"],
    "font-src": ["'self'", "data:"],

    // Same-origin only: every backend call goes through the /api/backend rewrite,
    // so the browser never addresses the API host directly. Anything added here
    // later is a new exfiltration channel and deserves the scrutiny.
    "connect-src": ["'self'"],

    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-src": ["'none'"],
    // Clickjacking. Supersedes X-Frame-Options where CSP is honoured; the header
    // is still sent for older agents.
    "frame-ancestors": ["'none'"],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    // Only meaningful over TLS, and in development everything is http.
    "upgrade-insecure-requests": isDevelopment ? null : [],
  };

  return Object.entries(directives)
    .filter(([, value]) => value !== null)
    .map(([name, value]) => (value!.length ? `${name} ${value!.join(" ")}` : name))
    .join("; ");
}

/**
 * Cryptographically random nonce, base64 for the CSP token grammar.
 *
 * Uses Web Crypto because the proxy runs on the edge/Node boundary where
 * `node:crypto` is not dependably available. `Math.random` would be unusable
 * here: a guessable nonce is an allow-list an attacker can satisfy.
 */
export function createNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
