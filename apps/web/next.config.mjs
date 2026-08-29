/**
 * Next.js configuration.
 *
 * Security headers live here rather than in `vercel.json` for two reasons: they
 * apply to static assets, which the proxy matcher deliberately skips, and they
 * remain in force on any host rather than only on Vercel. The Content-Security
 * -Policy is the exception — it needs a per-request nonce, so it is set in
 * `proxy.ts`.
 */

/** Headers that need no per-request value. */
const securityHeaders = [
  // Stop content-type sniffing turning an uploaded file into script.
  { key: "X-Content-Type-Options", value: "nosniff" },

  // CSP `frame-ancestors` supersedes this, but it is still honoured by older
  // agents that ignore the CSP directive.
  { key: "X-Frame-Options", value: "DENY" },

  // Send the origin cross-site, the full path same-site. Paths here carry
  // project ids, which do not belong in another site's referer logs.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },

  // Nothing in this product uses these, so they are denied rather than left at
  // the browser default.
  {
    key: "Permissions-Policy",
    value: [
      "accelerometer=()",
      "camera=()",
      "geolocation=()",
      "gyroscope=()",
      "magnetometer=()",
      "microphone=()",
      "payment=()",
      "usb=()",
    ].join(", "),
  },

  // Two years, subdomains included, and preload-eligible. Only meaningful over
  // TLS; harmless on plain http where browsers ignore it.
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },

  // Keeps Chrome from resolving hostnames found in page content.
  { key: "X-DNS-Prefetch-Control", value: "off" },

  // Isolates the browsing context from cross-origin openers and popups.
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // The framework version is not useful to a client and is useful to a scanner.
  poweredByHeader: false,

  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },

  async rewrites() {
    // Every browser call to the backend goes through this rewrite, which is what
    // keeps auth cookies first-party: the browser only ever addresses this
    // origin, so `SameSite=strict` works and the API host is never exposed to
    // the client. Do not replace this with direct calls to the API domain.
    const apiUrl = process.env.API_INTERNAL_URL || "http://localhost:8000";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
