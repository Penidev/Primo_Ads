"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { billingApi } from "@/lib/billing-api";
import { useLogout } from "@/hooks/useAuth";

export function DashboardTopbar() {
  const router = useRouter();
  const logout = useLogout();

  const { data: wallet } = useQuery({
    queryKey: ["wallet"],
    queryFn: () => billingApi.wallet(),
    retry: false,
  });

  const handleLogout = async () => {
    await logout.mutateAsync().catch(() => undefined);
    router.push("/login");
  };

  return (
    <header className="flex h-14 items-center justify-end gap-4 border-b border-neutral-800 px-6">
      <Link
        href="/dashboard/billing"
        className="text-sm text-neutral-300 hover:text-white"
      >
        Credits: {wallet ? wallet.balance_credits : "—"}
      </Link>
      <button
        type="button"
        onClick={handleLogout}
        className="text-sm text-neutral-400 hover:text-white"
        disabled={logout.isPending}
      >
        {logout.isPending ? "Signing out…" : "Sign out"}
      </button>
    </header>
  );
}
