/** Chart geometry for the sign-in panel. The figures live in `history.ts`. */

import { HISTORICAL_TICKERS, type HistoricalTicker } from "./history";

export type SampleTicker = HistoricalTicker;

export const SAMPLE_TICKERS: readonly SampleTicker[] = HISTORICAL_TICKERS;

/** The headline chart tracks the first ticker. */
export const FEATURED = SAMPLE_TICKERS[0];

export const CHART = {
  width: 560,
  height: 148,
} as const;

export const SPARKLINE = {
  width: 52,
  height: 18,
  /** Trailing closes shown in a row's trace -- roughly a month of trading. */
  samples: 22,
} as const;
