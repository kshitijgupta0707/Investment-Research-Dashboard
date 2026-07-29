"use client";

import { useState } from "react";

import { FEATURED } from "@/lib/market/sample";

import { LiveChart } from "./live-chart";
import { TickerTable } from "./ticker-table";

/** The chart and the rows beneath it, sharing one selected symbol. */
export function MarketBoard() {
  const [symbol, setSymbol] = useState(FEATURED.symbol);

  return (
    <>
      {/* `min-h-0` lets the chart shrink to fit rather than pushing the panel
          past the fold. */}
      <div className="mt-5 min-h-[150px] flex-1 lg:min-h-0">
        <LiveChart symbol={symbol} />
      </div>

      <TickerTable selected={symbol} onSelect={setSymbol} />
    </>
  );
}
