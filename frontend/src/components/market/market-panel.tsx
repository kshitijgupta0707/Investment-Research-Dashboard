import { BadgeCheck, Layers, Route } from "lucide-react";

import { BrandMark } from "@/components/brand/brand-mark";
import { SERIES_END } from "@/lib/market/history";

import { MarketBoard } from "./market-board";

/**
 * The left half of the sign-in screen.
 *
 * A server component that renders two client islands (the chart and the feed),
 * so the copy and layout ship as static markup and only the animation costs
 * JavaScript.
 */
export function MarketPanel() {
  return (
    // `lg:h-screen` plus `min-h-0` on the column below is what lets the chart
    // absorb the leftover space instead of the panel growing past the fold.
    <aside className="relative flex flex-col overflow-hidden border-b border-border px-6 py-7 lg:h-screen lg:border-b-0 lg:border-r lg:px-12 lg:py-9">
      <GridWash />

      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <BrandMark size="lg" />

        <h1 className="mt-5 max-w-[19ch] font-display text-[26px] font-medium leading-[1.14] tracking-[-0.03em] lg:mt-7 lg:text-[31px]">
          Days of desk work,{" "}
          <em className="not-italic text-primary">answered in minutes.</em>
        </h1>

        <p className="mt-3 max-w-[46ch] text-sm leading-relaxed text-muted-foreground">
          Ask an equity research question in plain language. An AI agent works out what it
          needs, gathers the data, and writes the report.
        </p>

        <Capabilities />

        <MarketBoard />

        <SampleDataNote />
      </div>
    </aside>
  );
}

/**
 * What the product actually does, in three claims.
 *
 * Specific rather than aspirational. "Powered by AI" tells a visitor nothing;
 * "a news question never touches the price feed" is a claim they can check in
 * thirty seconds, and it happens to be the hardest part of the system to build.
 */
const CAPABILITIES = [
  {
    icon: Route,
    title: "Chooses its own sources",
    detail: "A news question never touches the price feed.",
  },
  {
    icon: Layers,
    title: "Three sources, queried at once",
    detail: "Market data, news sentiment, and filing excerpts.",
  },
  {
    icon: BadgeCheck,
    title: "Every figure carries its source",
    detail: "With a timestamp and a confidence rating.",
  },
] as const;

function Capabilities() {
  return (
    <ul className="mt-5 shrink-0 space-y-2.5 lg:mt-6">
      {CAPABILITIES.map(({ icon: Icon, title, detail }) => (
        <li key={title} className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-primary/25 bg-primary/[0.08] text-primary"
          >
            <Icon className="h-3.5 w-3.5" />
          </span>
          <span className="min-w-0">
            <span className="block text-[13px] font-medium leading-snug">{title}</span>
            <span className="block text-[12px] leading-snug text-muted-foreground">{detail}</span>
          </span>
        </li>
      ))}
    </ul>
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
 * Dates the figures rather than implying they are current.
 *
 * These are real closing prices, but they were captured once and embedded --
 * nothing is fetched here, because there is no session yet. Presenting fixed
 * history as a live feed would be a small lie on the very screen that asks
 * people to trust the product's sourcing.
 */
function SampleDataNote() {
  return (
    <p className="numeric mt-4 flex items-center gap-2 text-[10.5px] tracking-wider text-faint">
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] rounded-full bg-primary shadow-[0_0_9px_hsl(var(--primary))]"
      />
      HISTORICAL CLOSES TO {SERIES_END} · NOT A LIVE FEED
    </p>
  );
}
