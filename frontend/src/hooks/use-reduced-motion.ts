"use client";

import { useEffect, useState } from "react";

/**
 * Whether the user has asked for reduced motion.
 *
 * Starts false and corrects after mount: the media query is unavailable during
 * server rendering, and defaulting to "motion is fine" keeps the markup stable
 * across hydration. Animations driven by this should be decorative only.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);

    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
