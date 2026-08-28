import type { ReactNode } from "react";
import { DashboardNav } from "@/components/layout/DashboardNav";

const nav = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/pricing", label: "Pricing" },
  { href: "/admin/models", label: "Video Models" },
  { href: "/admin/swipe-file", label: "Swipe File" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/security", label: "Security" },
  { href: "/admin/features", label: "Feature Flags" },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  // Admin access is enforced server-side by `require_admin` on every endpoint;
  // this layout is presentation only.
  return (
    <div className="min-h-screen lg:flex">
      <DashboardNav brand="Primo Admin" items={nav} />
      <main className="min-w-0 flex-1 p-4 sm:p-6">{children}</main>
    </div>
  );
}
