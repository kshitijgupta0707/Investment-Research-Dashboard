"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { SEEDS } from "@/lib/market/sample";
import { advance, randomWalk } from "@/lib/market/series";

import { useReducedMotion } from "./use-reduced-motion";

interface Options {
  samples: number;
  start: number;
  volatility: number;
  /** Milliseconds per sample. The line slides continuously between steps. */
  interval?: number;
}

/**
 * A scrolling sample series plus the sub-pixel offset that makes it glide.
 *
 * The offset is written straight to a ref's transform rather than held in
 * state: it changes every frame, and re-rendering the chart 60 times a second
 * to move it a fraction of a pixel would be wasteful. Only the series itself --
 * which changes once per `interval` -- lives in state.
 */
export function useLiveSeries({ samples, start, volatility, interval = 900 }: Options) {
  // Seeded, so the server-rendered prices match the browser's first paint.
  const [series, setSeries] = useState(() =>
    randomWalk(samples + 1, start, volatility, SEEDS.chart),
  );
  const trackRef = useRef<SVGGElement | null>(null);
  const reduced = useReducedMotion();

  const phase = useRef(0);
  const lastFrame = useRef(0);
  const frame = useRef(0);

  const step = useCallback(
    (time: number) => {
      if (!lastFrame.current) lastFrame.current = time;
      const elapsed = time - lastFrame.current;
      lastFrame.current = time;

      phase.current += elapsed / interval;
      if (phase.current >= 1) {
        phase.current -= 1;
        setSeries((current) => advance(current, volatility));
      }

      if (trackRef.current) {
        trackRef.current.style.setProperty("--slide", String(phase.current));
      }
      frame.current = requestAnimationFrame(step);
    },
    [interval, volatility],
  );

  useEffect(() => {
    if (reduced) return;
    frame.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame.current);
  }, [reduced, step]);

  return { series, trackRef };
}
