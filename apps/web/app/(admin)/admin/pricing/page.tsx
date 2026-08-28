"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/admin-api";

export default function AdminPricingPage() {
  const qc = useQueryClient();
  const [ratioDraft, setRatioDraft] = useState("");
  const [creditDrafts, setCreditDrafts] = useState<Record<string, string>>({});
  const [sceneSeconds, setSceneSeconds] = useState(6);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ratio = useQuery({ queryKey: ["admin-ratio"], queryFn: () => adminApi.getRatio() });
  const actions = useQuery({
    queryKey: ["admin-actions"],
    queryFn: () => adminApi.listActionPricing(),
  });
  const margins = useQuery({
    queryKey: ["admin-margins", sceneSeconds],
    queryFn: () => adminApi.margins(sceneSeconds),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin-ratio"] });
    qc.invalidateQueries({ queryKey: ["admin-actions"] });
    qc.invalidateQueries({ queryKey: ["admin-margins"] });
  };

  const saveRatio = useMutation({
    mutationFn: () => adminApi.setRatio(Number(ratioDraft)),
    onSuccess: () => {
      setRatioDraft("");
      setMessage("Credit value updated. All pricing recalculated.");
      setError(null);
      refresh();
    },
    onError: () => setError("Could not update the credit value."),
  });

  const saveAction = useMutation({
    mutationFn: ({ key, credits }: { key: string; credits: number }) =>
      adminApi.updateActionPricing(key, { base_credits: credits }),
    onSuccess: (_data, variables) => {
      setCreditDrafts((prev) => {
        const next = { ...prev };
        delete next[variables.key];
        return next;
      });
      setMessage("Action price updated.");
      setError(null);
      refresh();
    },
    onError: () => setError("Could not update that action price."),
  });

  const toggleAction = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      adminApi.updateActionPricing(key, { is_enabled: enabled }),
    onSuccess: refresh,
    onError: () => setError("Could not toggle that action."),
  });

  const unprofitable = (margins.data ?? []).filter((m) => !m.is_profitable);

  return (
    <div className="max-w-4xl space-y-10">
      <div>
        <h1 className="text-2xl font-semibold">Pricing</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Every price is read from the database at runtime. Changes apply immediately,
          with no deployment.
        </p>
      </div>

      {message && <p className="text-sm text-emerald-400">{message}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {/* --- credit value --- */}
      <section className="rounded-lg border border-neutral-800 p-5">
        <h2 className="font-medium">Credit value</h2>
        <p className="mt-1 text-xs text-neutral-500">
          The anchor for all pricing maths: what one credit is worth to a customer.
        </p>
        <div className="mt-4 flex items-end gap-3">
          <div>
            <p className="mb-1 text-xs text-neutral-500">Current</p>
            <p className="text-2xl font-semibold">
              ${ratio.data ? ratio.data.usd_per_credit.toFixed(2) : "—"}
              <span className="ml-1 text-sm font-normal text-neutral-500">/credit</span>
            </p>
          </div>
          <Input
            type="number"
            step="0.01"
            min="0.01"
            placeholder="New value"
            value={ratioDraft}
            onChange={(e) => setRatioDraft(e.target.value)}
            className="w-32"
          />
          <Button
            onClick={() => saveRatio.mutate()}
            disabled={!ratioDraft || saveRatio.isPending}
          >
            {saveRatio.isPending ? "Saving…" : "Update"}
          </Button>
        </div>
      </section>

      {/* --- per-action pricing --- */}
      <section>
        <h2 className="font-medium">Cost per action</h2>
        <div className="mt-3 divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {actions.data?.map((action) => (
            <div
              key={action.action_key}
              className="flex flex-wrap items-center gap-3 p-4"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-neutral-100">
                  {action.display_name ?? action.action_key}
                </p>
                <p className="text-xs text-neutral-500">
                  {action.action_key}
                  {action.unit && ` · ${action.unit}`}
                </p>
              </div>
              <span className="text-sm text-neutral-300">
                {action.base_credits} credits
              </span>
              <Input
                type="number"
                step="0.5"
                min="0"
                placeholder="New"
                value={creditDrafts[action.action_key] ?? ""}
                onChange={(e) =>
                  setCreditDrafts((prev) => ({
                    ...prev,
                    [action.action_key]: e.target.value,
                  }))
                }
                className="w-24"
              />
              <Button
                variant="outline"
                disabled={
                  !creditDrafts[action.action_key] || saveAction.isPending
                }
                onClick={() =>
                  saveAction.mutate({
                    key: action.action_key,
                    credits: Number(creditDrafts[action.action_key]),
                  })
                }
              >
                Save
              </Button>
              <button
                type="button"
                onClick={() =>
                  toggleAction.mutate({
                    key: action.action_key,
                    enabled: !action.is_enabled,
                  })
                }
                className={`rounded-full px-2 py-0.5 text-[11px] ${
                  action.is_enabled
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-neutral-700/50 text-neutral-400"
                }`}
              >
                {action.is_enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* --- margins --- */}
      <section>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-medium">Margin per scene</h2>
            <p className="mt-1 text-xs text-neutral-500">
              What a scene costs you at the provider versus what the customer pays.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-neutral-500">Scene length</span>
            <Input
              type="number"
              min="1"
              max="60"
              value={sceneSeconds}
              onChange={(e) => setSceneSeconds(Number(e.target.value) || 6)}
              className="w-20"
            />
            <span className="text-xs text-neutral-500">s</span>
          </div>
        </div>

        {unprofitable.length > 0 && (
          <p className="mt-3 rounded-md border border-red-900/60 bg-red-500/10 p-3 text-sm text-red-300">
            {unprofitable.length} model
            {unprofitable.length > 1 ? "s are" : " is"} priced at or below provider cost:{" "}
            {unprofitable.map((m) => m.slug).join(", ")}. Raise the multiplier or the
            credit value.
          </p>
        )}

        <div className="mt-3 overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
              <tr>
                <th className="p-3">Model</th>
                <th className="p-3">Your cost</th>
                <th className="p-3">Customer pays</th>
                <th className="p-3">Margin</th>
                <th className="p-3">%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {margins.data?.map((m) => (
                <tr key={m.slug} className={m.is_profitable ? "" : "bg-red-500/5"}>
                  <td className="p-3 text-neutral-200">{m.display_name ?? m.slug}</td>
                  <td className="p-3 text-neutral-400">
                    ${m.platform_cost_usd.toFixed(3)}
                  </td>
                  <td className="p-3 text-neutral-400">${m.user_price_usd.toFixed(2)}</td>
                  <td
                    className={`p-3 ${
                      m.is_profitable ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    ${m.margin_usd.toFixed(2)}
                  </td>
                  <td className="p-3 text-neutral-500">
                    {m.margin_percent !== null ? `${m.margin_percent}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
