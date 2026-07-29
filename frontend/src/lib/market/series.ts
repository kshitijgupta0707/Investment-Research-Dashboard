/**
 * Geometry helpers for the sign-in panel's charts. No React, no DOM.
 *
 * The numbers they project are real historical closes, in `history.ts`.
 */

export interface Point {
  x: number;
  y: number;
}

/**
 * Map values onto an SVG box, with vertical padding so peaks are not clipped.
 *
 * Pass an explicit `domain` unless the series is static — deriving the scale
 * from the values themselves makes the whole line jump whenever the high or low
 * changes.
 */
export function toPoints(
  values: number[],
  width: number,
  height: number,
  pad = 6,
  domain?: [number, number],
): Point[] {
  const min = domain ? domain[0] : Math.min(...values);
  const max = domain ? domain[1] : Math.max(...values);
  const range = max - min || 1;
  const lastIndex = values.length - 1 || 1;

  return values.map((value, index) => {
    const bounded = Math.min(max, Math.max(min, value));
    return {
      x: (index / lastIndex) * width,
      y: pad + (1 - (bounded - min) / range) * (height - pad * 2),
    };
  });
}

export function linePath(
  values: number[],
  width: number,
  height: number,
  pad = 6,
  domain?: [number, number],
): string {
  return toPoints(values, width, height, pad, domain)
    .map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join("");
}

/** The line, closed down to the baseline so it can be filled. */
export function areaPath(
  values: number[],
  width: number,
  height: number,
  pad = 6,
  domain?: [number, number],
): string {
  return `${linePath(values, width, height, pad, domain)}L${width},${height}L0,${height}Z`;
}

/** Where the leading edge of the line sits, for the tracking dot. */
export function latestY(
  values: number[],
  height: number,
  pad = 6,
  domain?: [number, number],
): number {
  const points = toPoints(values, 1, height, pad, domain);
  return points[points.length - 1]?.y ?? height / 2;
}
