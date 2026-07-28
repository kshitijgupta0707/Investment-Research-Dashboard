import type { Confidence } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const LEVELS: Record<Confidence, { bars: number; tone: string; hint: string }> = {
  high: { bars: 3, tone: "bg-up", hint: "Directly supported by the retrieved data" },
  medium: { bars: 2, tone: "bg-primary", hint: "A reasonable inference from the retrieved data" },
  low: {
    bars: 1,
    tone: "bg-down",
    hint: "The data is thin, stale, conflicting, or a source failed",
  },
};

/**
 * How well a section is supported by what was actually retrieved.
 *
 * Three filled bars plus the word, because the distinction is ordinal and a
 * colour alone would carry it only for sighted users. The tooltip explains what
 * the level means, since "medium confidence" is otherwise open to
 * interpretation.
 */
export function ConfidenceIndicator({
  level,
  className,
}: {
  level: Confidence;
  className?: string;
}) {
  const { bars, tone, hint } = LEVELS[level];

  return (
    <span className={cn("flex items-center gap-1.5", className)} title={hint}>
      <span aria-hidden="true" className="flex items-end gap-[2px]">
        {[1, 2, 3].map((bar) => (
          <span
            key={bar}
            className={cn(
              "w-[3px] rounded-[1px]",
              bar === 1 ? "h-[5px]" : bar === 2 ? "h-[8px]" : "h-[11px]",
              bar <= bars ? tone : "bg-border",
            )}
          />
        ))}
      </span>
      <span className="numeric text-[10px] uppercase tracking-wider text-faint">{level}</span>
    </span>
  );
}
