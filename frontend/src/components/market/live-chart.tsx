"use client";

import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { PRICE_HISTORY, SERIES_END } from "@/lib/market/history";
import { CHART, SAMPLE_TICKERS } from "@/lib/market/sample";
import { areaPath, latestY, linePath } from "@/lib/market/series";

import { Delta, directionColor } from "./delta";

const { width, height } = CHART;

/** A fixed y-scale for one symbol, so the line never re-scales under itself. */
function domainFor(series: number[]): [number, number] {
  const low = Math.min(...series);
  const high = Math.max(...series);
  const padding = (high - low) * 0.12 || 1;
  return [low - padding, high + padding];
}

/**
 * The headline chart on the sign-in panel.
 *
 * Selecting a different ticker replays the draw-on reveal rather than morphing
 * between paths, which reads as a smear. Ids are scoped with `useId` because
 * gradients and filters share a document-wide namespace.
 */
export function LiveChart({ symbol }: { symbol: string }) {
  const scope = useId().replace(/:/g, "");
  const fillId = `fill-${scope}`;
  const glowId = `glow-${scope}`;
  const reduced = useReducedMotion();

  const series = PRICE_HISTORY[symbol] ?? [];
  const ticker = SAMPLE_TICKERS.find((entry) => entry.symbol === symbol);
  const domain = domainFor(series);
  const stroke = directionColor(ticker?.changePercent ?? 0);

  return (
    <figure className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-gradient-to-b from-surface to-background/55">
      <figcaption className="flex shrink-0 items-baseline gap-3 px-4 pb-2 pt-3">
        <span className="numeric text-[13px] font-medium tracking-wider">{symbol}</span>
        <span
          className="numeric text-[19px] tabular-nums transition-colors duration-300"
          style={{ color: stroke }}
        >
          {ticker?.price.toFixed(2)}
        </span>
        <Delta value={ticker?.changePercent ?? 0} className="text-xs" />
        <span className="numeric ml-auto text-[10px] tracking-[0.1em] text-faint">
          6M · TO {SERIES_END}
        </span>
      </figcaption>

      {/* `preserveAspectRatio="none"` lets the viewBox stretch to fill whatever
          height is left over. */}
      <svg
        className="block min-h-0 w-full flex-1"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.26} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0} />
          </linearGradient>
          <filter id={glowId} x="-30%" y="-60%" width="160%" height="220%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1="0"
            y1={height * fraction}
            x2={width}
            y2={height * fraction}
            stroke="hsl(var(--hairline))"
            strokeWidth={1}
          />
        ))}

        {/* Keyed on the symbol so switching replays the reveal. */}
        <motion.path
          key={`area-${symbol}`}
          d={areaPath(series, width, height, 6, domain)}
          fill={`url(#${fillId})`}
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.4, ease: "easeOut" }}
        />

        {/* `pathLength` normalises the dash to 0-1, so no need to measure the
            path to animate it. */}
        <motion.path
          key={`line-${symbol}`}
          d={linePath(series, width, height, 6, domain)}
          fill="none"
          stroke={stroke}
          strokeWidth={1.8}
          strokeLinejoin="round"
          strokeLinecap="round"
          filter={`url(#${glowId})`}
          initial={reduced ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.1, ease: [0.33, 1, 0.68, 1] }}
        />

        <motion.circle
          key={`dot-${symbol}`}
          cx={width}
          cy={latestY(series, height, 6, domain)}
          r={3.2}
          fill={stroke}
          filter={`url(#${glowId})`}
          initial={reduced ? false : { opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 1, ease: "backOut" }}
        />
      </svg>
    </figure>
  );
}
