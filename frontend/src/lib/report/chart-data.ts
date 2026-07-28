import type { ChartContent } from "@/lib/api/types";

/** One x-axis position, with a value per series that reported at that date. */
export type ChartRow = { date: string } & Record<string, number | string | null>;

/**
 * Reshape the report's series-per-line into Recharts' row-per-date.
 *
 * The contract stores `[{label, points: [{date, value}]}]`, which is how the
 * agent thinks about it and how a chart is described. Recharts wants the
 * transpose. Series need not share dates -- a ticker that listed later simply
 * has no entry on earlier rows, and a null there makes Recharts break the line
 * rather than draw a false segment through the gap.
 */
export function toChartRows(content: ChartContent): ChartRow[] {
  const byDate = new Map<string, ChartRow>();

  for (const series of content.series) {
    for (const point of series.points) {
      const row = byDate.get(point.date) ?? { date: point.date };
      row[series.label] = point.value;
      byDate.set(point.date, row);
    }
  }

  const labels = content.series.map((series) => series.label);

  // `Array.from` rather than spreading the iterator: the tsconfig targets ES5
  // downlevel, where spreading a Map iterator needs `downlevelIteration`.
  return Array.from(byDate.values())
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((row) => {
      // Fill absent series explicitly: Recharts treats a missing key and a null
      // differently, and only the null produces a gap.
      for (const label of labels) {
        if (!(label in row)) row[label] = null;
      }
      return row;
    });
}

/**
 * Colours for the lines, drawn from the theme rather than invented.
 *
 * Cycles if a report compares more companies than there are slots, which is
 * better than running out and rendering an invisible line.
 */
export const SERIES_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--up))",
  "hsl(var(--down))",
  "hsl(var(--muted-foreground))",
  "hsl(var(--primary-dim))",
] as const;

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}
