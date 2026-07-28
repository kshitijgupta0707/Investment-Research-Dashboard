"use client";

import { useTickerFeed, type FeedRow } from "@/hooks/use-ticker-feed";
import { cn } from "@/lib/utils";

import { Delta } from "./delta";
import { Sparkline } from "./sparkline";

/** Illustrative rows that tick over, to give the panel a pulse. */
export function TickerTable() {
  const rows = useTickerFeed();

  return (
    <div className="mt-3 border-t border-border">
      {rows.map((row) => (
        <TickerRow key={row.symbol} row={row} />
      ))}
    </div>
  );
}

function TickerRow({ row }: { row: FeedRow }) {
  return (
    <div
      className={cn(
        "relative grid grid-cols-[56px_1fr_52px_auto_72px] items-center gap-3",
        "border-b border-hairline px-1 py-2 text-xs",
        // Rows beyond the third are noise on a phone, where the panel is a
        // header rather than the main event.
        "[&:nth-child(n+4)]:hidden sm:[&:nth-child(n+4)]:grid",
      )}
    >
      {row.flash ? <FlashOverlay direction={row.flash} revision={row.revision} /> : null}

      <span className="numeric font-medium tracking-wider">{row.symbol}</span>
      <span className="truncate text-xs text-faint">{row.name}</span>
      <Sparkline values={row.sparkline} change={row.changePercent} />
      <span className="numeric text-right text-muted-foreground">{row.price.toFixed(2)}</span>
      <Delta value={row.changePercent} className="text-right text-xs" />
    </div>
  );
}

/**
 * The green/red wash after a price move.
 *
 * Keyed on the row's revision so React remounts it and the CSS animation
 * replays; a stable key would leave a second move in the same direction
 * silently un-animated.
 */
function FlashOverlay({ direction, revision }: { direction: "up" | "down"; revision: number }) {
  return (
    <span
      key={revision}
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 animate-flash motion-reduce:hidden",
        direction === "up" ? "bg-up/[0.13]" : "bg-down/[0.13]",
      )}
    />
  );
}
