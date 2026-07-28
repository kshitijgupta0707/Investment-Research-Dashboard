import { BrandMark } from "@/components/brand/brand-mark";

import { LiveChart } from "./live-chart";
import { TickerTable } from "./ticker-table";

/**
 * The left half of the sign-in screen.
 *
 * A server component that renders two client islands (the chart and the feed),
 * so the copy and layout ship as static markup and only the animation costs
 * JavaScript.
 */
export function MarketPanel() {
  return (
    <aside className="relative flex flex-col overflow-hidden border-b border-border px-6 py-7 lg:border-b-0 lg:border-r lg:px-12 lg:py-10">
      <GridWash />

      <div className="relative z-10 flex flex-1 flex-col">
        <BrandMark />

        <h1 className="mt-6 max-w-[14ch] font-display text-[26px] font-medium leading-[1.14] tracking-[-0.03em] lg:mt-8 lg:text-[33px]">
          Days of desk work,{" "}
          <em className="not-italic text-primary">answered in minutes.</em>
        </h1>

        <p className="mt-3.5 max-w-[42ch] text-sm leading-relaxed text-muted-foreground">
          Ask in plain language. The agent decides which sources it needs, pulls them in
          parallel, and shows you where every number came from.
        </p>

        <div className="mt-6 lg:mt-auto">
          <LiveChart />
        </div>

        <TickerTable />

        <SampleDataNote />
      </div>
    </aside>
  );
}

/** Graph-paper wash plus a soft corner glow. Purely decorative. */
function GridWash() {
  return (
    <>
      <div aria-hidden="true" className="bg-grid mask-radial absolute inset-0 opacity-55" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-48 -top-56 h-[620px] w-[620px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, hsl(var(--primary) / 0.10), transparent 66%)",
        }}
      />
    </>
  );
}

/**
 * Says plainly that these figures are invented.
 *
 * Nothing has been fetched here -- there is no session yet, so there is no data
 * to fetch. Dressing a random walk up as "delayed quotes" would be a small lie
 * on the very screen that asks people to trust the product's sourcing.
 */
function SampleDataNote() {
  return (
    <p className="numeric mt-4 flex items-center gap-2 text-[10.5px] tracking-wider text-faint">
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] animate-pulse-dot rounded-full bg-primary shadow-[0_0_9px_hsl(var(--primary))] motion-reduce:animate-none"
      />
      SAMPLE DATA · NOT A LIVE FEED
    </p>
  );
}
