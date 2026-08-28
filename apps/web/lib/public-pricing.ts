/**
 * Server-side pricing fetch for the marketing pages.
 *
 * These run on the server so the pricing page is indexable, and they talk to the
 * API directly rather than through the browser proxy. A provider outage must not
 * break the marketing site, so every failure degrades to an empty list and the
 * page renders a fallback message.
 */

export interface PublicPlan {
  slug: string;
  display_name: string | null;
  price_usd: number;
  credits_per_month: number;
  billing_interval: string;
  features: Record<string, unknown> | null;
}

export interface PublicPackage {
  slug: string;
  display_name: string | null;
  price_usd: number;
  credits: number;
  bonus_credits: number;
}

const API_ROOT = process.env.API_INTERNAL_URL || "http://localhost:8000";

async function fetchPublic<T>(path: string): Promise<T[]> {
  try {
    const response = await fetch(`${API_ROOT}/api/v1${path}`, {
      // Always current: admin pricing edits must be visible immediately.
      cache: "no-store",
    });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? (data as T[]) : [];
  } catch {
    return [];
  }
}

export const getPlans = () => fetchPublic<PublicPlan>("/billing/plans");
export const getPackages = () => fetchPublic<PublicPackage>("/billing/packages");

/** Cost per credit, so buyers can compare packages honestly. */
export function perCreditUsd(priceUsd: number, credits: number): number | null {
  const total = credits;
  if (!total || total <= 0) return null;
  return priceUsd / total;
}
