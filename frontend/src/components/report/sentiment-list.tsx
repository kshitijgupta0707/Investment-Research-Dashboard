import { ExternalLink } from "lucide-react";

import type { SentimentContent } from "@/lib/api/types";

import { SentimentBadge } from "./sentiment-badge";

/**
 * The classified articles behind a sentiment section.
 *
 * Each headline links out to the original. The overall reading is stated
 * separately from the per-article ones rather than being derived here: it comes
 * from the model, which weighed substance over volume, and recomputing it as a
 * majority vote in the UI would quietly contradict the report.
 */
export function SentimentList({ content }: { content: SentimentContent }) {
  if (content.items.length === 0) {
    return <p className="text-xs text-faint">No articles were classified for this section.</p>;
  }

  return (
    <div>
      {content.overall ? (
        <div className="mb-3 flex items-center gap-2">
          <span className="numeric text-[10px] uppercase tracking-wider text-faint">
            Overall
          </span>
          <SentimentBadge sentiment={content.overall} />
        </div>
      ) : null}

      <ul className="divide-y divide-hairline">
        {content.items.map((item, index) => (
          <li key={`${item.headline}-${index}`} className="flex items-start gap-3 py-2.5">
            <SentimentBadge sentiment={item.sentiment} className="mt-0.5" />

            <div className="min-w-0 flex-1">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-start gap-1.5 text-[13px] leading-snug text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {item.headline}
                  <ExternalLink
                    className="mt-0.5 h-2.5 w-2.5 shrink-0 text-faint"
                    aria-hidden="true"
                  />
                </a>
              ) : (
                <span className="text-[13px] leading-snug text-muted-foreground">
                  {item.headline}
                </span>
              )}

              {item.ticker ? (
                <span className="numeric ml-2 text-[10px] tracking-wider text-faint">
                  {item.ticker}
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
