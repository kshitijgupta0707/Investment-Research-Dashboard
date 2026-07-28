import type { Source } from "@/lib/api/types";
import { absoluteTime, isStale } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * When the underlying figures were current.
 *
 * PROJECT_PLAN §3.10 is explicit that nothing in this product may be presented
 * as live: free market-data tiers serve delayed quotes, and a saved report is a
 * frozen snapshot besides. So wherever a provider gave a `data_as_of`, it is
 * shown — and past a day old it is called out rather than left to be inferred
 * from a timestamp the reader has to do arithmetic on.
 */
export function DataFreshnessLabel({
  sources,
  now,
  className,
}: {
  sources: Source[];
  now: number;
  className?: string;
}) {
  // The oldest stamp across a section's sources is the honest one: the section
  // is only as current as its stalest input.
  const stamps = sources
    .map((source) => source.data_as_of)
    .filter((value): value is string => Boolean(value))
    .sort();

  const oldest = stamps[0];
  if (!oldest) return null;

  return (
    <span
      className={cn("numeric text-[10px] text-faint", className)}
      title={`Provider reported this data as current at ${absoluteTime(oldest)}`}
    >
      Data as of {absoluteTime(oldest)}
      {isStale(oldest, now) ? " · delayed" : ""}
    </span>
  );
}
