"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminApi } from "@/lib/admin-api";

export default function AdminFeaturesPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const flags = useQuery({ queryKey: ["admin-flags"], queryFn: () => adminApi.listFlags() });

  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      adminApi.updateFlag(key, enabled),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["admin-flags"] });
    },
    onError: () => setError("Could not toggle that flag."),
  });

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Feature flags</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Turn capabilities on or off without a deployment. Useful for rolling out a new
          model or disabling something that misbehaves.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
        {flags.isLoading && <p className="p-4 text-sm text-neutral-500">Loading…</p>}
        {flags.data?.length === 0 && (
          <p className="p-4 text-sm text-neutral-500">No flags configured.</p>
        )}
        {flags.data?.map((flag) => (
          <div key={flag.key} className="flex items-center justify-between gap-4 p-4">
            <div className="min-w-0">
              <p className="text-sm text-neutral-100">{flag.key}</p>
              {flag.description && (
                <p className="mt-0.5 text-xs text-neutral-500">{flag.description}</p>
              )}
              <p className="mt-0.5 text-[11px] text-neutral-600">
                Applies to: {flag.applies_to}
              </p>
            </div>
            <button
              type="button"
              onClick={() => toggle.mutate({ key: flag.key, enabled: !flag.is_enabled })}
              disabled={toggle.isPending}
              aria-pressed={flag.is_enabled}
              className={`shrink-0 rounded-full px-3 py-1 text-xs transition disabled:opacity-50 ${
                flag.is_enabled
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "bg-neutral-700/50 text-neutral-400"
              }`}
            >
              {flag.is_enabled ? "Enabled" : "Disabled"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
