import type { Metadata } from "next";
import Link from "next/link";
import { Star } from "lucide-react";

import { EmptyState, ErrorState } from "@/components/states";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { AddTicker } from "@/components/watchlist/add-ticker";
import { RemoveTicker } from "@/components/watchlist/remove-ticker";
import { messageFor } from "@/lib/api/errors";
import { getWatchlist } from "@/lib/api/resources";
import type { WatchlistEntry } from "@/lib/api/types";
import { absoluteTime } from "@/lib/format";
import { routes } from "@/lib/routes";

export const metadata: Metadata = { title: "Watchlist" };

/** A pre-filled question, so a pinned company is one click from an answer. */
function analyseHref(entry: WatchlistEntry): string {
  const subject = entry.company_name ?? entry.ticker;
  const query = `Give me an overview of ${subject} (${entry.ticker}) — recent performance, major news, and key risks.`;
  return `${routes.research}?q=${encodeURIComponent(query)}`;
}

/**
 * The companies this analyst follows.
 *
 * Per-user, not shared: the API scopes every read and write to org *and* user,
 * so a colleague's watchlist is invisible here — unlike reports, which are
 * deliberately shared across the workspace.
 */
export default async function WatchlistPage() {
  let entries;
  try {
    entries = await getWatchlist();
  } catch (error) {
    return (
      <>
        <PageHeader title="Watchlist" description="The companies you follow." />
        <ErrorState detail={messageFor(error)} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Watchlist"
        description="Your own shortlist — colleagues in this workspace keep their own."
      />

      <div className="space-y-6">
        <Card className="bg-surface">
          <CardContent className="py-4">
            <AddTicker />
          </CardContent>
        </Card>

        {entries.length === 0 ? (
          <EmptyState
            icon={Star}
            title="Nothing pinned yet"
            hint="Add the companies you follow and each one is a click away from a fresh analysis."
          />
        ) : (
          <ul className="divide-y divide-hairline rounded-lg border border-border bg-surface">
            {entries.map((entry) => (
              <li key={entry.id} className="flex items-center gap-4 px-4 py-3">
                <span className="numeric w-16 shrink-0 text-sm font-medium tracking-wider">
                  {entry.ticker}
                </span>

                <span className="min-w-0 flex-1 truncate text-[13px] text-muted-foreground">
                  {entry.company_name ?? <span className="text-faint">—</span>}
                </span>

                <span
                  className="numeric hidden shrink-0 text-[10px] text-faint sm:inline"
                  title={absoluteTime(entry.created_at)}
                >
                  added {absoluteTime(entry.created_at).split(",")[0]}
                </span>

                <Link
                  href={analyseHref(entry)}
                  className="shrink-0 rounded-sm text-[12px] font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Analyse
                </Link>

                <RemoveTicker id={entry.id} ticker={entry.ticker} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
