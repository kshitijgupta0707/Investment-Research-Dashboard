import { linePath } from "@/lib/market/series";
import { SPARKLINE } from "@/lib/market/sample";

import { directionColor } from "./delta";

interface SparklineProps {
  values: number[];
  /** Direction of the parent row, so the trace matches its delta. */
  change: number;
}

/** A bare trend trace. Decorative: the row states the same figures in text. */
export function Sparkline({ values, change }: SparklineProps) {
  const { width, height } = SPARKLINE;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d={linePath(values, width, height, 3)}
        fill="none"
        stroke={directionColor(change)}
        strokeWidth={1.3}
        strokeLinejoin="round"
        opacity={0.85}
      />
    </svg>
  );
}
