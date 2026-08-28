"use client";

import { useId, useState } from "react";

/**
 * Accessible inline hint. Uses a real button with aria-describedby rather than a
 * hover-only tooltip, so the explanation is reachable by keyboard and screen
 * readers, not just a mouse.
 */
export function FieldHint({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={open ? "Hide explanation" : "Show explanation"}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
        className="ml-1.5 flex h-4 w-4 items-center justify-center rounded-full border border-neutral-600 text-[10px] leading-none text-neutral-400 transition hover:border-neutral-400 hover:text-neutral-200"
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="note"
          className="absolute left-6 top-0 z-10 w-64 rounded-md border border-neutral-700 bg-neutral-900 p-2.5 text-xs leading-relaxed text-neutral-300 shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  );
}

/** Label with an optional hint, used across the brief and onboarding forms. */
export function FieldLabel({
  children,
  hint,
  htmlFor,
}: {
  children: React.ReactNode;
  hint?: string;
  htmlFor?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 flex items-center text-sm text-neutral-300"
    >
      {children}
      {hint && <FieldHint text={hint} />}
    </label>
  );
}
