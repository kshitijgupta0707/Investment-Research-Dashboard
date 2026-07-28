/** Mirrors backend/app/schemas/watchlist.py. */
export const MAX_TICKER_CHARS = 12;

/** Allows the exchange-suffixed forms a real ticker takes: BRK.B, RY.TO. */
export const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.\-]*$/;

export type WatchlistState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "added"; ticker: string }
  | { status: "removed" };

export const idleWatchlistState: WatchlistState = { status: "idle" };
