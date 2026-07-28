/**
 * Geometry and sample-series helpers for the sign-in panel's charts.
 *
 * Pure functions with no React and no DOM, so they can be reasoned about and
 * tested on their own. The series they produce are **illustrative** -- a random
 * walk, not market data. Anything rendering them must say so; see
 * `components/market/`.
 */

export interface Point {
  x: number;
  y: number;
}

/**
 * A small deterministic PRNG (mulberry32).
 *
 * The sample series is rendered on the server and then hydrated in the browser.
 * `Math.random()` would produce a different walk in each, and React would report
 * the mismatched prices as a hydration error. Seeding makes the first paint
 * identical on both sides; the animation is free to diverge afterwards, because
 * by then hydration is done.
 */
function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * A bounded random walk, used only to animate the sample chart.
 *
 * Pass a `seed` for a reproducible series -- required anywhere the output is
 * server-rendered. Omit it for post-hydration steps.
 */
export function randomWalk(length: number, start: number, volatility = 1, seed?: number): number[] {
  const next = seed === undefined ? Math.random : seededRandom(seed);
  const series = [start];
  for (let i = 1; i < length; i += 1) {
    // Drift is very slightly positive so the sample line trends up over a
    // session instead of decaying towards the floor.
    series.push(Math.max(1, series[i - 1] + (next() - 0.48) * volatility));
  }
  return series;
}

/** Append one step, dropping the oldest, so the window length is constant. */
export function advance(series: number[], volatility = 1): number[] {
  const next = Math.max(1, series[series.length - 1] + (Math.random() - 0.47) * volatility);
  return [...series.slice(1), next];
}

/** Map values onto an SVG box, with vertical padding so peaks are not clipped. */
export function toPoints(values: number[], width: number, height: number, pad = 6): Point[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const lastIndex = values.length - 1 || 1;

  return values.map((value, index) => ({
    x: (index / lastIndex) * width,
    y: pad + (1 - (value - min) / range) * (height - pad * 2),
  }));
}

export function linePath(values: number[], width: number, height: number, pad = 6): string {
  return toPoints(values, width, height, pad)
    .map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join("");
}

/** The line, closed down to the baseline so it can be filled. */
export function areaPath(values: number[], width: number, height: number, pad = 6): string {
  return `${linePath(values, width, height, pad)}L${width},${height}L0,${height}Z`;
}

/** Where the leading edge of the line sits, for the tracking dot. */
export function latestY(values: number[], height: number, pad = 6): number {
  const points = toPoints(values, 1, height, pad);
  return points[points.length - 1]?.y ?? height / 2;
}

/** Percentage change across the whole window. */
export function percentChange(values: number[]): number {
  const first = values[0];
  const last = values[values.length - 1];
  if (!first) return 0;
  return ((last - first) / first) * 100;
}
