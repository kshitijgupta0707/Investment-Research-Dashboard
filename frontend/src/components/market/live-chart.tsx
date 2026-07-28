"use client";

import { useId } from "react";

import { useLiveSeries } from "@/hooks/use-live-series";
import { CHART, FEATURED, STEP } from "@/lib/market/sample";
import { areaPath, latestY, linePath, percentChange } from "@/lib/market/series";

import { Delta, directionColor } from "./delta";

const { width, height, samples, volatility } = CHART;

/**
 * The headline chart on the sign-in panel.
 *
 * The line is drawn one sample wider than the viewport and slid left by the
 * animation phase, so new points enter from the right edge rather than the
 * whole series jumping. Ids are scoped with `useId` because gradients and
 * filters share a document-wide namespace.
 */
export function LiveChart() {
  const { series, trackRef } = useLiveSeries({
    samples,
    start: FEATURED.price,
    volatility,
  });

  const scope = useId().replace(/:/g, "");
  const fillId = `fill-${scope}`;
  const glowId = `glow-${scope}`;
  const clipId = `clip-${scope}`;

  const change = percentChange(series);
  const stroke = directionColor(change);
  const price = series[series.length - 1];

  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-gradient-to-b from-surface to-background/55">
      <figcaption className="flex items-baseline gap-3 px-4 pb-2 pt-3">
        <span className="numeric text-[13px] font-medium tracking-wider">{FEATURED.symbol}</span>
        <span
          className="numeric text-[19px] tabular-nums transition-colors duration-500"
          style={{ color: stroke }}
        >
          {price.toFixed(2)}
        </span>
        <Delta value={change} className="text-xs" />
        <span className="numeric ml-auto text-[10px] tracking-[0.1em] text-faint">
          ILLUSTRATIVE
        </span>
      </figcaption>

      <svg
        className="block w-full"
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
          <clipPath id={clipId}>
            <rect x="0" y="0" width={width} height={height} />
          </clipPath>
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

        <g clipPath={`url(#${clipId})`}>
          <g
            ref={trackRef}
            style={{ transform: `translateX(calc(var(--slide, 0) * ${-STEP}px))` }}
          >
            <path d={areaPath(series, width + STEP, height)} fill={`url(#${fillId})`} />
            <path
              d={linePath(series, width + STEP, height)}
              fill="none"
              stroke={stroke}
              strokeWidth={1.8}
              strokeLinejoin="round"
              strokeLinecap="round"
              filter={`url(#${glowId})`}
            />
            <circle
              cx={width + STEP}
              cy={latestY(series, height)}
              r={3.2}
              fill={stroke}
              filter={`url(#${glowId})`}
            />
          </g>
        </g>
      </svg>
    </figure>
  );
}
