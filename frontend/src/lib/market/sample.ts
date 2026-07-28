/**
 * The illustrative tickers behind the sign-in panel.
 *
 * These are **not** market data. Nothing has been fetched: the figures are a
 * seeded random walk that exists to make an empty screen feel like the product.
 * Every surface that renders them is required to label them as illustrative --
 * a saved report's figures come from `data_as_of`-stamped providers and are a
 * different thing entirely.
 */

export interface SampleTicker {
  symbol: string;
  name: string;
  price: number;
  changePercent: number;
}

export const SAMPLE_TICKERS: readonly SampleTicker[] = [
  { symbol: "NVDA", name: "NVIDIA Corp", price: 184.22, changePercent: 2.41 },
  { symbol: "AMD", name: "Advanced Micro", price: 167.85, changePercent: -0.83 },
  { symbol: "INTC", name: "Intel Corp", price: 24.61, changePercent: 1.12 },
  { symbol: "TSLA", name: "Tesla Inc", price: 331.04, changePercent: -1.67 },
];

/** The headline chart tracks the first ticker. */
export const FEATURED = SAMPLE_TICKERS[0];

export const CHART = {
  width: 560,
  height: 148,
  /** Number of points in the visible window. */
  samples: 64,
  volatility: 1.7,
} as const;

/** One step's width, used to slide the line left by exactly one sample. */
export const STEP = CHART.width / CHART.samples;

export const SPARKLINE = { width: 52, height: 18, samples: 22 } as const;

/**
 * Fixed seeds for the initial, server-rendered series.
 *
 * Any figure that is rendered on the server and then hydrated must be identical
 * on both sides, so the starting walk cannot be drawn from `Math.random()`.
 * These make it reproducible; everything after mount is free to be random.
 */
export const SEEDS = { chart: 20260728, sparkline: 91217 } as const;
