"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { ChartContent } from "@/lib/api/types";
import { seriesColor, toChartRows } from "@/lib/report/chart-data";

/**
 * Historical price performance.
 *
 * Only rendered when the agent actually retrieved a series -- the synthesis
 * prompt says to use a chart section "only when a historical price series was
 * actually retrieved", so an empty one means something went wrong upstream and
 * is worth saying rather than drawing empty axes.
 */
export function PriceChart({ content }: { content: ChartContent }) {
  const rows = toChartRows(content);

  if (rows.length === 0 || content.series.length === 0) {
    return (
      <p className="text-xs text-faint">
        No price history was returned for this section.
      </p>
    );
  }

  const config: ChartConfig = Object.fromEntries(
    content.series.map((series, index) => [
      series.label,
      { label: series.label, color: seriesColor(index) },
    ]),
  );

  return (
    <ChartContainer config={config} className="h-[220px] w-full">
      <LineChart data={rows} margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--hairline))" />

        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={32}
          tickFormatter={shortDate}
          className="text-[10px]"
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={48}
          domain={["auto", "auto"]}
          className="text-[10px]"
          label={
            content.y_label
              ? {
                  value: content.y_label,
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 10, fill: "hsl(var(--faint))" },
                }
              : undefined
          }
        />

        <ChartTooltip content={<ChartTooltipContent labelFormatter={shortDate} />} />
        {content.series.length > 1 ? <ChartLegend content={<ChartLegendContent />} /> : null}

        {content.series.map((series, index) => (
          <Line
            key={series.label}
            type="monotone"
            dataKey={series.label}
            stroke={seriesColor(index)}
            strokeWidth={1.8}
            dot={false}
            // Draw a gap where a series has no point, rather than interpolating
            // across a date it never reported.
            connectNulls={false}
          />
        ))}
      </LineChart>
    </ChartContainer>
  );
}

/** "31 Jan" — enough to place a point without crowding the axis. */
function shortDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
