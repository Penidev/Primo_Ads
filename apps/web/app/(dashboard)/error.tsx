"use client";

import { SectionError } from "@/components/ui/section-error";

/** Scoped so a failure here keeps the dashboard navigation usable. */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <SectionError
      title="This page could not load"
      description="Your projects and credits are safe. Try again, or pick another page from the menu."
      digest={error.digest}
      reset={reset}
    />
  );
}
