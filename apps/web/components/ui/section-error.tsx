"use client";

import { Button } from "@/components/ui/button";

/**
 * Error state for a section boundary.
 *
 * Scoped boundaries matter here: a failure loading, say, the swipe-file library
 * should not blank the whole admin area, and the surrounding navigation should
 * stay usable so the user can go elsewhere.
 */
export function SectionError({
  title = "This section could not load",
  description = "Something went wrong fetching this data. Trying again usually resolves it.",
  digest,
  reset,
}: {
  title?: string;
  description?: string;
  digest?: string;
  reset: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-900/60 bg-red-500/5 p-8 text-center"
    >
      <h2 className="font-medium text-neutral-100">{title}</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm text-neutral-400">{description}</p>
      {digest && (
        <p className="mt-3 text-xs text-neutral-600">
          Reference: <code>{digest}</code>
        </p>
      )}
      <Button className="mt-6" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
