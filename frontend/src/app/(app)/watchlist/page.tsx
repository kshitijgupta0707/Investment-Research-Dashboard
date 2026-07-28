import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = { title: "Watchlist" };

/** Placeholder. Replaced by CR-24. */
export default function WatchlistPage() {
  return (
    <ComingSoon
      title="Watchlist"
      description="The companies you follow."
      cr="Coming in Next CR's"
      scope="Add and remove tickers, each linking through to a pre-filled analysis."
    />
  );
}
