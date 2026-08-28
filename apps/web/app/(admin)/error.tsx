"use client";

import { SectionError } from "@/components/ui/section-error";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <SectionError
      title="This admin page could not load"
      description="If this persists, check that the API is reachable and that your account still has admin access."
      digest={error.digest}
      reset={reset}
    />
  );
}
