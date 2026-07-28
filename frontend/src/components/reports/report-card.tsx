import Link from "next/link";

import { TagList } from "@/components/reports/tag-list";
import { Card, CardContent } from "@/components/ui/card";
import type { ReportSummary } from "@/lib/api/types";
import { absoluteTime, isStale, relativeTime } from "@/lib/format";
import { routes } from "@/lib/routes";

/** One row in the saved-reports list. */
export function ReportCard({ report, now }: { report: ReportSummary; now: number }) {
  return (
    <Card className="bg-surface/40 transition-colors hover:border-primary-dim">
      <CardContent className="py-4">
        <Link
          href={`${routes.reports}/${report.id}`}
          className="block rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <h3 className="text-sm leading-snug hover:text-primary">{report.query_text}</h3>
        </Link>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <TagList tags={report.tags} linked />

          <span
            className="numeric text-[10px] text-faint"
            title={absoluteTime(report.created_at)}
          >
            {report.created_by_email} · {relativeTime(report.created_at, now)}
          </span>

          {/* A saved report speaks for the day it was written, not today. */}
          {isStale(report.created_at, now) ? (
            <span
              className="numeric text-[10px] uppercase tracking-wider text-faint"
              title="Figures are as of the date this report was generated"
            >
              Snapshot
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
