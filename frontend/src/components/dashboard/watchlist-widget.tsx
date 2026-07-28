import Link from "next/link";
import { Star } from "lucide-react";

import { EmptyState, ErrorState } from "@/components/states";
import { messageFor } from "@/lib/api/errors";
import { getWatchlist } from "@/lib/api/resources";
import type { WatchlistEntry } from "@/lib/api/types";
import { routes } from "@/lib/routes";

import { Widget } from "./index";

/** A pre-filled research question, so a pinned ticker is one click from an answer. */
function analyseHref(entry: WatchlistEntry): string {
  const subject = entry.company_name ?? entry.ticker;
  const query = `Give me an overview of ${subject} (${entry.ticker}) — recent performance, major news, and key risks.`;
  return `${routes.research}?q=${encodeURIComponent(query)}`;
}

/** The caller's pinned companies. Per-user, not shared across the org. */
export async function WatchlistWidget() {
  let entries;
  try {
    entries = await getWatchlist();
  } catch (error) {
    return (
      <Widget title="Watchlist">
        <ErrorState inline detail={messageFor(error)} />
      </Widget>
    );
  }

  if (entries.length === 0) {
    return (
      <Widget title="Watchlist">
        <EmptyState
          icon={Star}
          title="Nothing pinned yet"
          hint="Pin the companies you follow to keep them one click from a fresh analysis."
          action={{ href: routes.watchlist, label: "Add a company" }}
        />
      </Widget>
    );
  }

  return (
    <Widget title="Watchlist" href={routes.watchlist} linkLabel="Manage">
      <ul className="divide-y divide-hairline">
        {entries.map((entry) => (
          <li key={entry.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
            <span className="numeric w-14 shrink-0 text-xs font-medium tracking-wider">
              {entry.ticker}
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-faint">
              {entry.company_name ?? "—"}
            </span>
            <Link
              href={analyseHref(entry)}
              className="shrink-0 rounded-sm text-[11px] font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Analyse
            </Link>
          </li>
        ))}
      </ul>
    </Widget>
  );
}
