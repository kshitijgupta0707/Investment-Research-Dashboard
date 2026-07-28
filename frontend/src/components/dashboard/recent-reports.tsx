import Link from "next/link";
import { FileText } from "lucide-react";

import { EmptyState, ErrorState } from "@/components/states";
import { TagList } from "@/components/reports/tag-list";
import { messageFor } from "@/lib/api/errors";
import { getRecentReports } from "@/lib/api/resources";
import type { ReportSummary } from "@/lib/api/types";
import { absoluteTime, isStale, relativeTime, truncate } from "@/lib/format";
import { routes } from "@/lib/routes";

import { Widget } from "./index";

/**
 * Recently saved reports across the whole organization.
 *
 * Org-wide rather than per-user, because a workspace is shared -- seeing a
 * colleague's work here is the intended behaviour, not a leak.
 */
export async function RecentReports({ now }: { now: number }) {
  let page;
  try {
    page = await getRecentReports(5);
  } catch (error) {
    return (
      <Widget title="Saved reports">
        <ErrorState inline detail={messageFor(error)} />
      </Widget>
    );
  }

  if (page.items.length === 0) {
    return (
      <Widget title="Saved reports">
        <EmptyState
          icon={FileText}
          title="No saved reports yet"
          hint="Run a query, then save the result to keep it — reports are shared with everyone in your workspace."
          action={{ href: routes.research, label: "Run a query" }}
        />
      </Widget>
    );
  }

  return (
    <Widget title="Saved reports" href={routes.reports}>
      <ul className="divide-y divide-hairline">
        {page.items.map((report) => (
          <ReportRow key={report.id} report={report} now={now} />
        ))}
      </ul>
    </Widget>
  );
}

function ReportRow({ report, now }: { report: ReportSummary; now: number }) {
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <Link
        href={`${routes.reports}/${report.id}`}
        className="block rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <p className="text-sm leading-snug hover:text-primary" title={report.query_text}>
          {truncate(report.query_text)}
        </p>
      </Link>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <TagList tags={report.tags} max={3} />
        <span className="numeric text-[10px] text-faint" title={absoluteTime(report.created_at)}>
          {report.created_by_email} · {relativeTime(report.created_at, now)}
        </span>
        {/* A saved report is a frozen snapshot; past a day its figures may
            have moved. PROJECT_PLAN §3.10 asks for that to be visible. */}
        {isStale(report.created_at, now) ? (
          <span
            className="numeric text-[10px] uppercase tracking-wider text-faint"
            title="Figures are as of the date this report was generated"
          >
            Snapshot
          </span>
        ) : null}
      </div>
    </li>
  );
}
