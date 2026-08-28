"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

interface NavItem {
  href: string;
  label: string;
}

interface Props {
  brand: string;
  items: NavItem[];
}

/**
 * Responsive navigation shell.
 *
 * On small screens the sidebar collapses into a slide-over drawer; on desktop it
 * is a permanent column. The drawer closes on route change so a tap on a link
 * does not leave it hanging open.
 */
export function DashboardNav({ brand, items }: Props) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [lastPathname, setLastPathname] = useState(pathname);

  // Close the drawer whenever navigation happens, including via the back button.
  // Adjusting state during render is React's documented alternative to calling
  // setState inside an effect, and it avoids the extra commit-then-rerender pass
  // that briefly painted the drawer open over the new page.
  if (lastPathname !== pathname) {
    setLastPathname(pathname);
    setOpen(false);
  }

  const isActive = (href: string) =>
    pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));

  const links = (
    <nav aria-label="Dashboard" className="flex flex-col gap-1">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={isActive(item.href) ? "page" : undefined}
          className={`rounded-md px-3 py-2 text-sm transition ${
            isActive(item.href)
              ? "bg-neutral-800 text-white"
              : "text-neutral-300 hover:bg-neutral-900"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );

  return (
    <>
      {/* Mobile bar */}
      <div className="flex items-center justify-between border-b border-neutral-800 px-4 py-3 lg:hidden">
        <Link href="/dashboard" className="text-lg font-bold">
          {brand}
        </Link>
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300"
        >
          Menu
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/60"
          />
          <div className="absolute left-0 top-0 h-full w-64 border-r border-neutral-800 bg-neutral-950 p-4">
            <div className="mb-6 flex items-center justify-between">
              <span className="text-lg font-bold">{brand}</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className="text-sm text-neutral-400 hover:text-white"
              >
                Close
              </button>
            </div>
            {links}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-neutral-800 p-4 lg:flex">
        <Link href="/dashboard" className="mb-8 text-lg font-bold">
          {brand}
        </Link>
        {links}
      </aside>
    </>
  );
}
