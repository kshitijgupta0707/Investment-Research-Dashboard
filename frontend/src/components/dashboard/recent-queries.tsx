import { Search } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { StatusDot } from "@/components/research/status-dot";
import { ToolBadges } from "@/components/research/tool-badges";
import { getRecentQueries } from "@/lib/api/resources";
import type { QueryHistoryEntry } from "@/lib/api/types";
import { messageFor } from "@/lib/api/errors";
import { absoluteTime, relativeTime, seconds, truncate } from "@/lib/format";
import { routes } from "@/lib/routes";

import { Widget, WidgetError } from "./index";

/**
 * The last few questions this analyst asked, saved or not.
 *
 * History is per-user (unlike reports, which are shared across the org), so
 * this is the one panel that is genuinely *theirs*.
 */
export async function RecentQueries({ now }: { now: number }) {
  let page;
  try {
    page = await getRecentQueries(5);
  } catch (error) {
    return (
      <Widget title="Recent queries">
        <WidgetError detail={messageFor(error)} />
      </Widget>
    );
  }

  if (page.items.length === 0) {
    return (
      <Widget title="Recent queries">
        <EmptyState
          icon={Search}
          title="You haven't run a query yet"
          hint="Ask a question in plain language — the agent works out which sources it needs."
          action={{ href: routes.research, label: "Start your first research" }}
        />
      </Widget>
    );
  }

  return (
    <Widget title="Recent queries" href={routes.research} linkLabel="New research">
      <ul className="divide-y divide-hairline">
        {page.items.map((entry) => (
          <QueryRow key={entry.id} entry={entry} now={now} />
        ))}
      </ul>
    </Widget>
  );
}

function QueryRow({ entry, now }: { entry: QueryHistoryEntry; now: number }) {
  const latency = seconds(entry.latency_ms);

  return (
    <li className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
      <StatusDot status={entry.status} className="mt-1.5" />

      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug" title={entry.query_text}>
          {truncate(entry.query_text)}
        </p>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <ToolBadges tools={entry.tools_selected} />
          <span
            className="numeric text-[10px] text-faint"
            title={absoluteTime(entry.created_at)}
          >
            {relativeTime(entry.created_at, now)}
            {latency ? ` · ${latency}` : ""}
          </span>
        </div>
      </div>
    </li>
  );
}
