import type { Sentiment } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TONES: Record<Sentiment, { className: string; glyph: string }> = {
  positive: { className: "border-up/40 bg-up/10 text-up", glyph: "▲" },
  negative: { className: "border-down/40 bg-down/10 text-down", glyph: "▼" },
  neutral: { className: "border-border bg-surface text-muted-foreground", glyph: "■" },
};

/**
 * How one article reads for the company holding the stock.
 *
 * Classified by the LLM from the headline and description -- NewsAPI does not
 * supply sentiment, and the brief requires the model to judge it rather than a
 * separate classifier.
 *
 * The glyph carries the same meaning as the colour, so the badge still works
 * without colour vision.
 */
export function SentimentBadge({
  sentiment,
  className,
}: {
  sentiment: Sentiment;
  className?: string;
}) {
  const { className: tone, glyph } = TONES[sentiment];

  return (
    <span
      className={cn(
        "numeric inline-flex shrink-0 items-center gap-1 rounded-sm border px-1.5 py-0.5",
        "text-[10px] uppercase tracking-wider",
        tone,
        className,
      )}
    >
      <span aria-hidden="true">{glyph}</span>
      {sentiment}
    </span>
  );
}
