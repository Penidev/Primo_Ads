"use client";

import { useQuery } from "@tanstack/react-query";
import { billingApi } from "@/lib/billing-api";

export default function BillingPage() {
  const wallet = useQuery({ queryKey: ["wallet"], queryFn: () => billingApi.wallet() });
  const plans = useQuery({ queryKey: ["plans"], queryFn: () => billingApi.plans() });
  const packages = useQuery({
    queryKey: ["packages"],
    queryFn: () => billingApi.packages(),
  });
  const transactions = useQuery({
    queryKey: ["transactions"],
    queryFn: () => billingApi.transactions(),
  });

  return (
    <div className="max-w-3xl space-y-10">
      <section>
        <h1 className="text-2xl font-semibold">Credits & billing</h1>
        <div className="mt-4 rounded-lg border border-neutral-800 p-5">
          <p className="text-sm text-neutral-400">Current balance</p>
          <p className="mt-1 text-3xl font-semibold">
            {wallet.data ? wallet.data.balance_credits : "—"}
            <span className="ml-2 text-base font-normal text-neutral-500">credits</span>
          </p>
          {wallet.data && (
            <p className="mt-1 text-xs text-neutral-500">
              Approx. ${wallet.data.estimated_usd_value.toFixed(2)} of value · $
              {wallet.data.usd_per_credit.toFixed(2)} per credit
            </p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-medium">Subscription plans</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {plans.data?.map((plan) => (
            <div key={plan.slug} className="rounded-lg border border-neutral-800 p-4">
              <p className="font-medium">{plan.display_name ?? plan.slug}</p>
              <p className="mt-1 text-2xl font-semibold">
                ${plan.price_usd}
                <span className="text-sm font-normal text-neutral-500">
                  /{plan.billing_interval === "monthly" ? "mo" : plan.billing_interval}
                </span>
              </p>
              <p className="mt-1 text-sm text-neutral-400">
                {plan.credits_per_month} credits per month
              </p>
            </div>
          ))}
          {plans.data?.length === 0 && (
            <p className="text-sm text-neutral-500">No plans configured yet.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-medium">Top up</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {packages.data?.map((pkg) => (
            <div key={pkg.slug} className="rounded-lg border border-neutral-800 p-4">
              <p className="font-medium">{pkg.display_name ?? pkg.slug}</p>
              <p className="mt-1 text-2xl font-semibold">${pkg.price_usd}</p>
              <p className="mt-1 text-sm text-neutral-400">
                {pkg.credits}
                {pkg.bonus_credits > 0 && ` + ${pkg.bonus_credits} bonus`} credits
              </p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-neutral-500">
          Checkout (Stripe, PayPal, Cozzipay) is enabled in the payments phase.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-medium">Recent activity</h2>
        <div className="mt-3 divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {transactions.data?.length === 0 && (
            <p className="p-4 text-sm text-neutral-500">No transactions yet.</p>
          )}
          {transactions.data?.map((tx) => (
            <div key={tx.id} className="flex items-center justify-between p-3 text-sm">
              <div className="min-w-0">
                <p className="truncate text-neutral-200">
                  {tx.description ?? tx.transaction_type}
                </p>
                <p className="text-xs text-neutral-500">
                  {new Date(tx.created_at).toLocaleString()}
                </p>
              </div>
              <span
                className={tx.amount < 0 ? "text-neutral-300" : "text-emerald-400"}
              >
                {tx.amount > 0 ? "+" : ""}
                {tx.amount}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
