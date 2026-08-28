/**
 * Constrain a post-login redirect to a same-site path.
 *
 * The `next` parameter is attacker-controllable: anyone can send a victim a link
 * to `/login?next=<somewhere>`. Without this check that becomes an open redirect
 * onto a look-alike sign-in page, which is a credible phishing vector.
 *
 * Anything that is not a plain absolute path on this origin falls back to the
 * dashboard. Rejected forms include:
 *   - absolute URLs (`https://evil.test`)
 *   - protocol-relative URLs (`//evil.test`), which browsers treat as absolute
 *   - scheme-relative tricks (`/\evil.test`), which some browsers normalise
 *   - non-HTTP schemes (`javascript:`)
 *   - backslash and encoded variants that normalise to the above
 */
export const DEFAULT_REDIRECT = "/dashboard";

export function safeRedirect(
  target: string | null | undefined,
  fallback: string = DEFAULT_REDIRECT
): string {
  if (!target) return fallback;

  // Reject control characters and whitespace outright; they are used to smuggle
  // past naive prefix checks.
  if (/[\s\u0000-\u001f\u007f]/.test(target)) return fallback;

  // Normalise backslashes, which several browsers treat as forward slashes.
  const normalised = target.replace(/\\/g, "/");

  // Must be an absolute path on this origin.
  if (!normalised.startsWith("/")) return fallback;

  // `//host` and `/\host` are protocol-relative, so they leave the origin.
  if (normalised.startsWith("//")) return fallback;

  return normalised;
}
