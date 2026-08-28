import type { ReactNode } from "react";
import { DashboardNav } from "@/components/layout/DashboardNav";
import { DashboardTopbar } from "@/components/layout/DashboardTopbar";

const nav = [
  { href: "/dashboard", label: "Home" },
  { href: "/dashboard/projects", label: "Projects" },
  { href: "/dashboard/billing", label: "Billing" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:flex">
      <DashboardNav brand="Primo" items={nav} />
      <div className="flex min-w-0 flex-1 flex-col">
        <DashboardTopbar />
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
