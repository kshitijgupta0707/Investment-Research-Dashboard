"use client";

import { useEffect, useState } from "react";

import { randomWalk } from "@/lib/market/series";
import { SAMPLE_TICKERS, SEEDS, SPARKLINE, type SampleTicker } from "@/lib/market/sample";

import { useReducedMotion } from "./use-reduced-motion";

export type Direction = "up" | "down";

export interface FeedRow extends SampleTicker {
  sparkline: number[];
  /** Set for one tick after a change, to drive the row flash. */
  flash: Direction | null;
  /**
   * Increments on every price move. Used as the flash element's key so the
   * animation replays even when the direction repeats -- a stable key would
   * leave the element mounted and the CSS animation would not re-fire.
   */
  revision: number;
}

function seed(): FeedRow[] {
  // Each row gets its own offset from a fixed base, so the traces differ from
  // one another but stay identical between the server render and hydration.
  return SAMPLE_TICKERS.map((ticker, index) => ({
    ...ticker,
    sparkline: randomWalk(
      SPARKLINE.samples,
      ticker.price,
      ticker.price * 0.012,
      SEEDS.sparkline + index,
    ),
    flash: null,
    revision: 0,
  }));
}

/**
 * Illustrative ticker rows that tick over on an interval.
 *
 * Roughly half the rows move on each pass rather than all of them, which reads
 * as a feed rather than a metronome. Frozen entirely under reduced motion.
 */
export function useTickerFeed(intervalMs = 1500): FeedRow[] {
  const [rows, setRows] = useState<FeedRow[]>(seed);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;

    const id = setInterval(() => {
      setRows((current) =>
        current.map((row) => {
          if (Math.random() > 0.55) return row.flash ? { ...row, flash: null } : row;

          const drift = (Math.random() - 0.5) * 0.34;
          const price = Number((row.price * (1 + drift / 100)).toFixed(2));

          return {
            ...row,
            price,
            changePercent: Number((row.changePercent + drift).toFixed(2)),
            sparkline: [...row.sparkline.slice(1), price],
            flash: drift >= 0 ? "up" : "down",
            revision: row.revision + 1,
          };
        }),
      );
    }, intervalMs);

    return () => clearInterval(id);
  }, [intervalMs, reduced]);

  return rows;
}
