import type { Metadata } from "next";
import Link from "next/link";
import { getPackages, getPlans, perCreditUsd } from "@/lib/public-pricing";

export const metadata: Metadata = {
  title: "Pricing — Primo",
  description:
    "Prepaid credits for AI ad production. Pay for the scripts and video you generate, with no minimum commitment.",
};

/**
 * Rendered per request rather than prerendered.
 *
 * Prices are admin-editable at runtime, and the API is not necessarily reachable
 * at build time — static generation would bake in whatever was true (or
 * unavailable) when the image was built. Correct prices matter more here than
 * shaving a few milliseconds off a low-traffic marketing page.
 */
export const dynamic = "force-dynamic";

const INCLUDED = [
  "Strategic brief intake and AI creative direction",
  "Scene-by-scene script with camera, lighting and grading notes",
  "Brand-consistent reference assets",
  "Your choice of video engine",
  "Automatic stitching to a finished master file",
  "Treatment, shot list and prompt exports",
];

export default async function PricingPage() {
  // Fetched in parallel: neither list depends on the other.
  const [plans, packages] = await Promise.all([getPlans(), getPackages()]);
  const unavailable = plans.length === 0 && packages.length === 0;

  return (
    <main className="px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <header className="text-center">
          <h1 className="text-4xl font-bold">Pricing</h1>
          <p className="mx-auto mt-4 max-w-xl text-neutral-400">
            Credits are prepaid and spent only on what you generate. Scripts cost a
            fraction of a video, and failed generations are refunded automatically.
          </p>
        </header>

        {unavailable && (
          <p className="mt-12 rounded-lg border border-neutral-800 p-8 text-center text-neutral-400">
            Pricing is being updated. Please check back shortly, or{" "}
            <Link href="/register" className="text-brand-highlight hover:underline">
              create an account
            </Link>{" "}
            to see current rates.
          </p>
        )}

        {plans.length > 0 && (
          <section className="mt-14">
            <h2 className="text-lg font-medium">Monthly plans</h2>
            <p className="mt-1 text-sm text-neutral-500">
              A credit allowance every month, best if you produce ads regularly.
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              {plans.map((plan, index) => {
                const featured = index === 1;
                return (
                  <div
                    key={plan.slug}
                    className={`relative rounded-xl border p-6 ${
                      featured
                        ? "border-brand bg-brand/5"
                        : "border-neutral-800"
                    }`}
                  >
                    {featured && (
                      <span className="absolute -top-2.5 left-6 rounded-full bg-brand px-2 py-0.5 text-[11px] font-medium text-white">
                        Most popular
                      </span>
                    )}
                    <h3 className="font-medium text-neutral-100">
                      {plan.display_name ?? plan.slug}
                    </h3>
                    <p className="mt-3">
                      <span className="text-3xl font-semibold">
                        ${plan.price_usd}
                      </span>
                      <span className="text-sm text-neutral-500">
                        /
                        {plan.billing_interval === "monthly"
                          ? "month"
                          : plan.billing_interval}
                      </span>
                    </p>
                    <p className="mt-2 text-sm text-neutral-300">
                      {plan.credits_per_month.toLocaleString()} credits per month
                    </p>
                    <Link
                      href="/register"
                      className={`mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition ${
                        featured
                          ? "bg-brand text-white hover:opacity-90"
                          : "border border-neutral-700 text-neutral-200 hover:bg-neutral-900"
                      }`}
                    >
                      Get started
                    </Link>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {packages.length > 0 && (
          <section className="mt-14">
            <h2 className="text-lg font-medium">Pay as you go</h2>
            <p className="mt-1 text-sm text-neutral-500">
              One-off credit top-ups with no subscription. Credits do not expire.
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              {packages.map((pkg) => {
                const total = pkg.credits + pkg.bonus_credits;
                const rate = perCreditUsd(pkg.price_usd, total);
                return (
                  <div
                    key={pkg.slug}
                    className="rounded-xl border border-neutral-800 p-6"
                  >
                    <h3 className="font-medium text-neutral-100">
                      {pkg.display_name ?? pkg.slug}
                    </h3>
                    <p className="mt-3 text-3xl font-semibold">${pkg.price_usd}</p>
                    <p className="mt-2 text-sm text-neutral-300">
                      {pkg.credits.toLocaleString()} credits
                      {pkg.bonus_credits > 0 && (
                        <span className="text-emerald-400">
                          {" "}
                          + {pkg.bonus_credits} bonus
                        </span>
                      )}
                    </p>
                    {rate !== null && (
                      <p className="mt-1 text-xs text-neutral-500">
                        ${rate.toFixed(3)} per credit
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        <section className="mt-16 rounded-xl border border-neutral-800 p-8">
          <h2 className="text-lg font-medium">Every plan includes</h2>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {INCLUDED.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-neutral-300">
                <span aria-hidden="true" className="text-brand-highlight">
                  &#10003;
                </span>
                {item}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-14">
          <h2 className="text-lg font-medium">How credits are spent</h2>
          <div className="mt-4 overflow-x-auto rounded-xl border border-neutral-800">
            <table className="w-full text-sm">
              <caption className="sr-only">Credit cost by action</caption>
              <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
                <tr>
                  <th scope="col" className="p-4">
                    Action
                  </th>
                  <th scope="col" className="p-4">
                    What you get
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800 text-neutral-300">
                <tr>
                  <td className="p-4">Script &amp; direction</td>
                  <td className="p-4 text-neutral-400">
                    Full scene-by-scene treatment. Cheap enough to iterate on.
                  </td>
                </tr>
                <tr>
                  <td className="p-4">Reference assets</td>
                  <td className="p-4 text-neutral-400">
                    Brand-accurate images per scene. Upload your own for free.
                  </td>
                </tr>
                <tr>
                  <td className="p-4">Video generation</td>
                  <td className="p-4 text-neutral-400">
                    Priced by engine — budget models cost a fraction of premium ones.
                  </td>
                </tr>
                <tr>
                  <td className="p-4">Stitching &amp; exports</td>
                  <td className="p-4 text-neutral-400">
                    Included at no extra cost.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-neutral-500">
            Exact credit costs are shown before you confirm any generation. If a
            scene fails, its credits are returned automatically.
          </p>
        </section>

        <div className="mt-16 text-center">
          <Link
            href="/register"
            className="inline-block rounded-lg bg-brand px-6 py-3 font-medium text-white transition hover:opacity-90"
          >
            Start your first ad
          </Link>
        </div>
      </div>
    </main>
  );
}
