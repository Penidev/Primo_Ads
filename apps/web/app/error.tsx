"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Root error boundary.
 *
 * Catches anything thrown during rendering that a nested boundary did not
 * handle. Deliberately shows a generic message: an exception can carry internal
 * detail (query fragments, paths, provider responses) that should not reach a
 * user's screen. The digest is surfaced instead, so a support conversation can
 * be tied back to the server log.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Logged client-side; the server-side counterpart is captured by Sentry.
    console.error("Unhandled application error:", error.message);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-semibold">Something went wrong</h1>
        <p className="mt-3 text-sm text-neutral-400">
          This page failed to load. Your work is saved — nothing is lost by trying
          again.
        </p>
        {error.digest && (
          <p className="mt-4 text-xs text-neutral-600">
            Reference: <code>{error.digest}</code>
          </p>
        )}
        <div className="mt-8 flex justify-center gap-3">
          <Button onClick={reset}>Try again</Button>
          <Link href="/dashboard">
            <Button variant="outline">Back to dashboard</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
