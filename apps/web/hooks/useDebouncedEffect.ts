"use client";

import { useEffect, useRef } from "react";

/**
 * Run `effect` after `delay` ms of no changes to `deps`.
 * Used for auto-saving the brief without hammering the API.
 */
export function useDebouncedEffect(
  effect: () => void,
  deps: unknown[],
  delay = 800
) {
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const timer = setTimeout(effect, delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, delay]);
}
