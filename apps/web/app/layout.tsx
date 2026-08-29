import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Primo — AI Ad Production Studio",
  description:
    "Generate strategic ad concepts, directorial scripts, and finished videos with AI.",
};

/**
 * Required by the Content-Security-Policy, not a performance choice.
 *
 * The CSP in `proxy.ts` carries a per-request script nonce. Next only stamps that
 * nonce onto its hydration scripts while rendering HTML per request — a
 * statically prerendered page has its script tags baked at build time with no
 * nonce, so the policy blocks the framework's own scripts and the page renders
 * blank.
 *
 * This was verified rather than assumed: with static rendering, zero of fifteen
 * script tags on /login carried a nonce while the header demanded one.
 *
 * The cost is HTML served per request instead of from the edge cache. Static
 * assets (JS and CSS chunks) are unaffected and still cache normally. Worth it:
 * the alternative is `script-src 'unsafe-inline'`, which also permits any
 * injected script and leaves CSP doing almost nothing about XSS.
 */
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
