import { cn } from "@/lib/utils";

interface DeltaProps {
  /** Percentage change. Sign decides both the glyph and the colour. */
  value: number;
  className?: string;
  /** Render only the arrow, for use beside a figure that carries its own value. */
  glyphOnly?: boolean;
}

/**
 * A signed percentage, coloured by direction.
 *
 * The one place in the app that decides what "up" looks like. Colour alone
 * would fail for colour-blind readers, so the arrow carries the same meaning
 * and screen readers get the word.
 */
export function Delta({ value, className, glyphOnly = false }: DeltaProps) {
  const rising = value >= 0;

  return (
    <span className={cn("numeric", rising ? "text-up" : "text-down", className)}>
      <span aria-hidden="true">{rising ? "▲" : "▼"}</span>
      <span className="sr-only">{rising ? "up" : "down"} </span>
      {!glyphOnly && ` ${Math.abs(value).toFixed(2)}%`}
    </span>
  );
}

/** The colour a direction should paint with, for SVG strokes and fills. */
export function directionColor(value: number): string {
  return value >= 0 ? "hsl(var(--up))" : "hsl(var(--down))";
}
