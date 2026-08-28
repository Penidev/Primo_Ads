"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { adminApi } from "@/lib/admin-api";
import { swipeFileApi } from "@/lib/swipe-file-api";

const SHORTCUTS = [
  {
    href: "/admin/pricing",
    title: "Pricing",
    description: "Credit value, per-action costs, and margin analysis.",
  },
  {
    href: "/admin/models",
    title: "Video models",
    description: "Register engines, set multipliers, enable or disable.",
  },
  {
    href: "/admin/swipe-file",
    title: "Swipe file",
    description: "Analyse reference ads and approve blueprints.",
  },
  {
    href: "/admin/users",
    title: "Users",
    description: "Accounts, suspensions, and manual credit grants.",
  },
  {
    href: "/admin/features",
    title: "Feature flags",
    description: "Toggle capabilities without deploying.",
  },
] as const;

export default function AdminOverview() {
  const models = useQuery({
    queryKey: ["admin-models"],
    queryFn: () => adminApi.listModels(),
    retry: false,
  });
  const margins = useQuery({
    queryKey: ["admin-margins", 6],
    queryFn: () => adminApi.margins(6),
    retry: false,
  });
  const swipe = useQuery({
    queryKey: ["swipe-stats"],
    queryFn: () => swipeFileApi.stats(),
    retry: false,
  });
  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminApi.listUsers(200),
    retry: false,
  });

  const enabledModels = (models.data ?? []).filter((m) => m.is_enabled).length;
  const unprofitable = (margins.data ?? []).filter((m) => !m.is_profitable);
  const approvedBlueprints = swipe.data?.approved ?? 0;

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Admin overview</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Operational health and quick access to controls.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: "Users", value: users.data?.length ?? "—" },
          { label: "Enabled models", value: enabledModels || "—" },
          { label: "Approved blueprints", value: approvedBlueprints },
          { label: "Pending review", value: swipe.data?.pending ?? "—" },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border border-neutral-800 p-4">
            <p className="text-xs text-neutral-500">{item.label}</p>
            <p className="mt-1 text-2xl font-semibold">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Surface the two conditions that actually break the product. */}
      {approvedBlueprints === 0 && (
        <p className="rounded-md border border-amber-900/60 bg-amber-500/10 p-3 text-sm text-amber-300">
          No approved blueprints yet, so scripts are generated without reference
          patterns.{" "}
          <Link href="/admin/swipe-file" className="underline">
            Add reference ads
          </Link>
          .
        </p>
      )}
      {unprofitable.length > 0 && (
        <p className="rounded-md border border-red-900/60 bg-red-500/10 p-3 text-sm text-red-300">
          {unprofitable.length} model{unprofitable.length > 1 ? "s are" : " is"} priced
          at or below provider cost.{" "}
          <Link href="/admin/pricing" className="underline">
            Review pricing
          </Link>
          .
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {SHORTCUTS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-lg border border-neutral-800 p-4 transition hover:border-neutral-600"
          >
            <p className="font-medium text-neutral-100">{item.title}</p>
            <p className="mt-1 text-sm text-neutral-500">{item.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
