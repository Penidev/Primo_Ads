import Link from "next/link";
import type { ReactNode } from "react";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-neutral-800">
        <nav
          aria-label="Main"
          className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4"
        >
          <Link href="/" className="text-lg font-bold">
            Primo
          </Link>
          <div className="flex items-center gap-5 text-sm">
            <Link href="/pricing" className="text-neutral-300 hover:text-white">
              Pricing
            </Link>
            <Link href="/login" className="text-neutral-300 hover:text-white">
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-brand px-4 py-2 font-medium text-white transition hover:opacity-90"
            >
              Get started
            </Link>
          </div>
        </nav>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="border-t border-neutral-800">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-6 py-8 text-sm text-neutral-500 sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; {new Date().getFullYear()} Primo. All rights reserved.</p>
          <div className="flex gap-5">
            <Link href="/pricing" className="hover:text-neutral-300">
              Pricing
            </Link>
            <Link href="/login" className="hover:text-neutral-300">
              Sign in
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
