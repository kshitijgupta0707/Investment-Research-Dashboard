"use client";

import { motion, useReducedMotion } from "framer-motion";

import { PRICE_HISTORY } from "@/lib/market/history";
import { SAMPLE_TICKERS, SPARKLINE, type SampleTicker } from "@/lib/market/sample";
import { cn } from "@/lib/utils";

import { Delta } from "./delta";
import { Sparkline } from "./sparkline";

interface TickerTableProps {
  selected: string;
  onSelect: (symbol: string) => void;
}

/**
 * Closing figures for the sampled symbols. Selecting one drives the chart above.
 *
 * Rows are buttons rather than clickable divs, so they are keyboard reachable
 * and carry `aria-pressed`.
 */
export function TickerTable({ selected, onSelect }: TickerTableProps) {
  const reduced = useReducedMotion();

  return (
    <div className="mt-3 border-t border-border">
      {SAMPLE_TICKERS.map((ticker, index) => (
        <motion.div
          key={ticker.symbol}
          initial={reduced ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 + index * 0.07, ease: "easeOut" }}
          className={cn(
            // Beyond the third is noise on a phone.
            index >= 3 && "hidden sm:block",
          )}
        >
          <TickerRow
            ticker={ticker}
            active={ticker.symbol === selected}
            onSelect={() => onSelect(ticker.symbol)}
          />
        </motion.div>
      ))}
    </div>
  );
}

function TickerRow({
  ticker,
  active,
  onSelect,
}: {
  ticker: SampleTicker;
  active: boolean;
  onSelect: () => void;
}) {
  const closes = PRICE_HISTORY[ticker.symbol] ?? [];
  const trace = closes.slice(-SPARKLINE.samples);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      aria-label={`Show the ${ticker.name} chart`}
      className={cn(
        "relative grid w-full grid-cols-[56px_1fr_52px_auto_72px] items-center gap-3",
        "border-b border-hairline px-1 py-2 text-left text-xs transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "bg-primary/[0.06]" : "hover:bg-surface-raised/60",
      )}
    >
      {/* Accent rail on the active row, matching the sidebar's own convention
          for "this is the one you are looking at". */}
      {active ? (
        <motion.span
          layoutId="ticker-active"
          aria-hidden="true"
          transition={{ type: "spring", stiffness: 420, damping: 34 }}
          className="absolute inset-y-1 left-0 w-[2px] rounded-full bg-primary"
        />
      ) : null}

      <span
        className={cn(
          "numeric font-medium tracking-wider transition-colors",
          active ? "text-primary" : "text-foreground",
        )}
      >
        {ticker.symbol}
      </span>
      <span className="truncate text-xs text-faint">{ticker.name}</span>
      <Sparkline values={trace} change={ticker.changePercent} />
      <span className="numeric text-right text-muted-foreground">{ticker.price.toFixed(2)}</span>
      <Delta value={ticker.changePercent} className="text-right text-xs" />
    </button>
  );
}
